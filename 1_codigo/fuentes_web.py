# CineCaptions · By Cinema Productions
# 1_codigo/fuentes_web.py — v5.5.3: FOTOS de internet con licencia para el B-roll de la Edición PRO (escena FotoE y fotos de tablero/polaroid).
"""
Cuando se habla de algo concreto («perritos», «desnutrición», «la ciudad»), la Edición PRO puede enseñar una FOTO REAL de ese tema. Solo de bancos
cuya licencia permite usarla en el video de un cliente (uso comercial y modificación):

    Openverse          (sin clave)   CC0, dominio público y CC BY      — api.openverse.org
    Wikimedia Commons  (sin clave)   CC0, dominio público y CC BY      — commons.wikimedia.org
    Pexels / Pixabay   (clave gratuita del usuario, la del B-roll de Efectos: sirve una u otra)   licencia propia, sin atribución obligatoria

NUNCA CC BY-SA (obligaría a compartir el video con la misma licencia) ni NC/ND (prohíben el uso comercial o modificar). NO se usa Google ni
Pinterest: sus imágenes tienen derechos de autor y prohíben la descarga automática (el usuario recibiría reclamaciones de copyright).
El crédito de cada foto CC BY va en la propia escena (letra pequeña) y en ~/DaVinciSubtitles/creditos_broll.txt (para la descripción del video).

    buscar_foto(consulta, formato='v', claves=None, evitar=())  -> {'archivo', 'ancho', 'alto', 'credito', 'licencia', 'fuente', 'pagina', 'id'} | None
    foto_data_uri(info, lado=1080)                             -> 'data:image/jpeg;base64,…' (para las props de Remotion)
    anotar_creditos(fotos, video)                              (los CC BY, en creditos_broll.txt)
    hay_red()                                                  (una comprobación rápida; sin red no se pierde tiempo)
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import ssl
import time
import urllib.parse
import urllib.request
from pathlib import Path

AGENTE = 'CineCaptions/5.5 (+https://github.com/AlejandroPiedrasanta/CineCaptions-releases)'
CACHE = Path.home() / 'DaVinciSubtitles' / 'broll_cache' / 'fotos'
CREDITOS = Path.home() / 'DaVinciSubtitles' / 'creditos_broll.txt'
LADO_MIN = 900                     # la foto tapa la pantalla: más pequeña se vería borrosa
TIMEOUT = 9
# palabras que, en el título o las etiquetas, descartan una foto (nada explícito ni morboso en el video de un cliente)
VETADAS = set('''nude naked nudity nsfw porn sex sexy erotic topless lingerie corpse dead death body autopsy gore blood bloody wound injury surgery
surgical dying war weapon gun rifle execution torture skeleton cadaver kwashiorkor marasmus'''.split())
_RED = {'ok': None, 't': 0.0}


def _ssl():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return None


def _json(url, headers=None, timeout=TIMEOUT):
    req = urllib.request.Request(url, headers={'User-Agent': AGENTE, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl()) as r:
        return json.loads(r.read().decode('utf-8'))


def _bytes(url, timeout=20, maximo=12 << 20):
    req = urllib.request.Request(url, headers={'User-Agent': AGENTE})
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl()) as r:
        datos = r.read(maximo + 1)
    if len(datos) > maximo:
        raise ValueError('imagen demasiado grande')
    return datos


def hay_red(timeout=4):
    """¿Hay internet? (se recuerda 2 minutos)."""
    if _RED['ok'] is not None and time.time() - _RED['t'] < 120:
        return _RED['ok']
    try:
        _json('https://api.openverse.org/v1/images/?q=test&page_size=1', timeout=timeout)
        ok = True
    except Exception:
        ok = False
    _RED.update(ok=ok, t=time.time())
    return ok


def claves(op=None):
    """{'pexels': …, 'pixabay': …} desde la clave del B-roll de Efectos (una sola casilla: se reconoce cuál es por su forma)."""
    try:
        if op is None:
            import efectos_visuales
            op = efectos_visuales.opciones_guardadas()
    except Exception:
        op = op or {}
    out = {}
    for k in (str(op.get('pexels_key') or '').strip(), str(op.get('pixabay_key') or '').strip()):
        if re.fullmatch(r'\d{5,10}-[0-9a-f]{20,40}', k):
            out['pixabay'] = k                                               # las de Pixabay: «12345678-0a1b2c…»
        elif len(k) >= 30:
            out['pexels'] = k
    return out


def _malo(*textos):
    t = ' '.join(str(x or '') for x in textos).lower()
    return any(w in VETADAS for w in re.findall(r'[a-z]+', t))


def _limpio(html):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', str(html or ''))).strip()[:60]


# ----------------------------------------------------------------------------------------------------------------------------- fuentes
def _openverse(consulta, formato):
    q = {'q': consulta, 'license': 'cc0,pdm,by', 'page_size': 20, 'mature': 'false'}
    d = _json('https://api.openverse.org/v1/images/?' + urllib.parse.urlencode(q))
    out = []
    for x in d.get('results') or []:
        w, h = int(x.get('width') or 0), int(x.get('height') or 0)
        if max(w, h) < LADO_MIN or _malo(x.get('title'), ' '.join(t.get('name', '') for t in x.get('tags') or [] if isinstance(t, dict))):
            continue
        lic = str(x.get('license') or '').lower()
        out.append({'url': x.get('url'), 'ancho': w, 'alto': h, 'fuente': 'Openverse · ' + str(x.get('source') or ''), 'id': 'ov_' + str(x.get('id')),
                    'licencia': 'CC0' if lic == 'cc0' else 'Dominio público' if lic == 'pdm' else f"CC BY {x.get('license_version') or ''}".strip(),
                    'autor': _limpio(x.get('creator')), 'pagina': x.get('foreign_landing_url') or '',
                    'titulo': (str(x.get('title') or '') + ' ' + ' '.join(t.get('name', '') for t in x.get('tags') or [] if isinstance(t, dict)))[:300]})
    return out


def _commons(consulta, formato):
    q = {'action': 'query', 'format': 'json', 'generator': 'search', 'gsrnamespace': 6, 'gsrsearch': f'{consulta} filetype:bitmap', 'gsrlimit': 20,
         'prop': 'imageinfo', 'iiprop': 'url|size|extmetadata|mime', 'iiurlwidth': 1440}
    d = _json('https://commons.wikimedia.org/w/api.php?' + urllib.parse.urlencode(q))
    out = []
    for p in ((d.get('query') or {}).get('pages') or {}).values():
        ii = (p.get('imageinfo') or [{}])[0]
        md = ii.get('extmetadata') or {}
        lic = str((md.get('LicenseShortName') or {}).get('value') or '')
        l2 = lic.lower()
        if not (l2.startswith('cc by') and 'sa' not in l2 and 'nc' not in l2 and 'nd' not in l2) and not ('public domain' in l2 or l2.startswith('cc0') or l2 == 'pd'):
            continue
        w, h = int(ii.get('width') or 0), int(ii.get('height') or 0)
        if max(w, h) < LADO_MIN or str(ii.get('mime')) not in ('image/jpeg', 'image/png') or _malo(p.get('title'), (md.get('ImageDescription') or {}).get('value'),
                                                                                                   (md.get('Categories') or {}).get('value')):
            continue
        out.append({'url': ii.get('thumburl') or ii.get('url'), 'ancho': w, 'alto': h, 'fuente': 'Wikimedia Commons', 'id': 'wc_' + str(p.get('pageid')),
                    'licencia': 'Dominio público' if 'public' in l2 or l2 == 'pd' else lic, 'autor': _limpio((md.get('Artist') or {}).get('value')),
                    'pagina': ii.get('descriptionurl') or '',
                    'titulo': (str(p.get('title') or '') + ' ' + _limpio((md.get('Categories') or {}).get('value')))[:300]})
    return out


def _pexels(consulta, formato, clave):
    orient = {'v': 'portrait', 'h': 'landscape'}.get(formato, 'square')
    d = _json('https://api.pexels.com/v1/search?' + urllib.parse.urlencode({'query': consulta, 'orientation': orient, 'per_page': 15}),
              headers={'Authorization': clave})
    return [{'url': (x.get('src') or {}).get('large2x') or (x.get('src') or {}).get('original'), 'ancho': int(x.get('width') or 0), 'alto': int(x.get('height') or 0),
             'fuente': 'Pexels', 'id': 'px_' + str(x.get('id')), 'licencia': 'Licencia de Pexels', 'autor': _limpio(x.get('photographer')), 'pagina': x.get('url') or ''}
            for x in d.get('photos') or [] if not _malo(x.get('alt'))]


def _pixabay(consulta, formato, clave):
    orient = {'v': 'vertical', 'h': 'horizontal'}.get(formato, 'all')
    d = _json('https://pixabay.com/api/?' + urllib.parse.urlencode({'key': clave, 'q': consulta, 'image_type': 'photo', 'orientation': orient, 'safesearch': 'true',
                                                                       'per_page': 20, 'min_width': LADO_MIN}))
    return [{'url': x.get('largeImageURL'), 'ancho': int(x.get('imageWidth') or 0), 'alto': int(x.get('imageHeight') or 0), 'fuente': 'Pixabay',
             'id': 'pb_' + str(x.get('id')), 'licencia': 'Licencia de Pixabay', 'autor': _limpio(x.get('user')), 'pagina': x.get('pageURL') or ''}
            for x in d.get('hits') or [] if not _malo(x.get('tags'))]


def _puntos(c, formato):
    """Lo que mejor llena la pantalla: la orientación del video, buena resolución, y las de bancos de stock primero."""
    w, h = max(1, c['ancho']), max(1, c['alto'])
    vertical = h >= w
    p = 0.0
    p += 3.0 if (formato == 'v') == vertical else 0.0
    p += min(2.0, min(w, h) / 1080.0)
    p += {'Pexels': 2.0, 'Pixabay': 1.6}.get(c['fuente'], 0.0) + (0.4 if c['fuente'].startswith('Openverse') else 0.0)
    return p


# ----------------------------------------------------------------------------------------------------------------------------- buscar
def _cache_consulta(consulta, formato):
    return CACHE / ('q2_' + hashlib.sha1(f'{consulta}|{formato}'.encode('utf-8')).hexdigest()[:16] + '.json')   # (q2: v5.5.4, con el título)


def candidatos(consulta, formato='v', claves_=None):
    """Las fotos que valen para esa consulta, de todas las fuentes (con caché de 30 días por consulta)."""
    consulta = ' '.join(str(consulta or '').split())[:60]
    if not consulta:
        return []
    cache = _cache_consulta(consulta, formato)
    try:
        if cache.exists() and time.time() - cache.stat().st_mtime < 30 * 86400:
            return json.loads(cache.read_text(encoding='utf-8'))
    except Exception:
        pass
    claves_ = claves_ if claves_ is not None else claves()
    todos = []
    fuentes = []
    if claves_.get('pexels'):
        fuentes.append(lambda: _pexels(consulta, formato, claves_['pexels']))
    if claves_.get('pixabay'):
        fuentes.append(lambda: _pixabay(consulta, formato, claves_['pixabay']))
    fuentes += [lambda: _openverse(consulta, formato), lambda: _commons(consulta, formato)]
    from concurrent.futures.thread import ThreadPoolExecutor      # v5.41: 3.15 la expone «lazy» en el paquete y el .exe no la despertaba

    def una(f):
        try:
            return [c for c in f() if c.get('url')]
        except Exception:
            return []
    with ThreadPoolExecutor(len(fuentes)) as ex:                      # las fuentes a la vez (cada API tarda lo suyo)
        for r in ex.map(una, fuentes):
            todos += r
    todos.sort(key=lambda c: -_puntos(c, formato))
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(todos[:24], ensure_ascii=False), encoding='utf-8')
    except Exception:
        pass
    return todos[:24]


# v5.5.8: fotos que no se ponen nunca en el video de un cliente (título o etiquetas de la foto): tragedias, violencia, muerte, desnudos, política
VETADAS = frozenset('''crush memorial memorials death dead deaths died dying funeral funerals grave graves cemetery corpse corpses killed killing kill
murder murdered victim victims tragedy tragic disaster disasters accident accidents crash crashed wreck explosion bombing bomb bombs war wars warfare
battle soldier soldiers military army weapon weapons gun guns rifle shooting shooter terror terrorist terrorism attack attacks riot riots protest
protests protesters police arrest arrested prison jail blood bloody injury injured wound wounded burning burned flood flooding
earthquake hurricane refugee refugees starvation poverty nude nudity naked sex sexual erotic lingerie drug drugs cocaine smoking cigarette nazi
swastika genocide holocaust execution hanging suicide abuse riotpolice demonstration election campaign politician president minister'''.split())


# v5.5.8: fotos que casi siempre son un cartel, una pancarta o una captura con texto (a pantalla completa se ven feas): fuera con `sin_texto`
CON_TEXTO = frozenset('''summit conference conclave ceremony award awards seminar meeting forum expo exhibition banner poster posters flyer leaflet
logo logos sign signs signage billboard advertisement advert screenshot diagram chart graph map infographic certificate document documents
newspaper magazine cover album label brochure slide slides presentation keynote convention congress'''.split())


def buscar_foto(consulta, formato='v', claves_=None, evitar=(), exigir='', sin_atribucion=False, sin_texto=False):
    """La mejor foto para `consulta` (en inglés), DESCARGADA en la caché, o None (sin red, sin resultados o todas fallan). `exigir` (v5.5.4): una
    palabra que tiene que estar en el título o las etiquetas de la foto (la de un LUGAR que se nombra: que sea de verdad de ese sitio).
    `sin_atribucion` (v5.5.8): solo las que no piden el crédito EN el video (CC0, dominio público, Pexels, Pixabay): para las tarjetas,
    polaroids y tableros, que no lo enseñan (el crédito va igual a creditos_broll.txt)."""
    if not hay_red():
        return None
    exigir = _plegar_simple(exigir)
    for c in candidatos(consulta, formato, claves_):
        if c['id'] in evitar or (exigir and exigir not in _plegar_simple(c.get('titulo'))):
            continue
        if sin_atribucion and str(c.get('licencia') or '').startswith('CC BY'):
            continue
        if VETADAS & set(_plegar_simple(c.get('titulo')).split()):
            continue                                                       # v5.5.8: «festival» devolvía el memorial de una tragedia
        if sin_texto and CON_TEXTO & set(_plegar_simple(c.get('titulo')).split()):
            continue                                                       # v5.5.8: «emprendimientos» devolvía la pancarta de un congreso
        destino = CACHE / (re.sub(r'[^\w.-]', '_', c['id']) + '.jpg')
        try:
            if not destino.exists() or destino.stat().st_size < 10000:
                datos = _bytes(c['url'])
                from PIL import Image
                im = Image.open(io.BytesIO(datos)).convert('RGB')
                if max(im.size) < LADO_MIN * 0.8:
                    continue
                im.thumbnail((1600, 1600))
                CACHE.mkdir(parents=True, exist_ok=True)
                im.save(destino, 'JPEG', quality=88)
            return dict(c, archivo=str(destino), credito=credito(c))
        except Exception:
            continue
    return None


def _plegar_simple(t):
    import unicodedata
    t = unicodedata.normalize('NFD', str(t or '').lower())
    return re.sub(r'[^a-z0-9 ]', ' ', ''.join(ch for ch in t if unicodedata.category(ch) != 'Mn')).strip()


def credito(c):
    """El crédito que se ve en la escena: obligatorio en CC BY, cortesía en los demás."""
    autor = re.split(r'\s{2,}|[,;(]| - ', str(c.get('autor') or ''))[0].strip()[:28]
    fuente = str(c.get('fuente') or '').split(' · ')[0]
    if c.get('licencia', '').startswith('CC BY'):
        return f"Foto: {autor or 'autor'} · {c['licencia']} · {fuente}"
    return f"Foto: {autor} · {fuente}" if autor and fuente in ('Pexels', 'Pixabay') else f"Foto: {fuente}"


def foto_data_uri(info, lado=1080):
    """La foto descargada como data URI JPEG (lo que Remotion pinta sin tocar la red)."""
    try:
        from PIL import Image
        im = Image.open(info['archivo']).convert('RGB')
        im.thumbnail((lado, lado))
        b = io.BytesIO()
        im.save(b, 'JPEG', quality=86)
        return 'data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode('ascii')
    except Exception:
        return ''


def anotar_creditos(fotos, video=''):
    """Las fotos usadas en este GO, con autor, licencia y enlace, al final de creditos_broll.txt (para copiarlas a la descripción del video)."""
    fotos = [f for f in fotos if f]
    if not fotos:
        return
    try:
        CREDITOS.parent.mkdir(parents=True, exist_ok=True)
        lineas = [f"\n== {time.strftime('%Y-%m-%d %H:%M')} · {Path(str(video)).name or 'video'}"]
        lineas += [f"- {f.get('autor') or 'autor desconocido'} · {f.get('licencia')} · {f.get('fuente')} · {f.get('pagina')}" for f in fotos]
        with open(CREDITOS, 'a', encoding='utf-8') as fh:
            fh.write('\n'.join(lineas) + '\n')
    except Exception:
        pass
