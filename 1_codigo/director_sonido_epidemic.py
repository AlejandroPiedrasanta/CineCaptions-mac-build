# CineCaptions · By Cinema Productions
# 1_codigo/director_sonido_epidemic.py — «AI Sound Director»: cliente de la API de Epidemic Sound (solo backend; la clave, solo del entorno).
"""
LA CLAVE: solo de la variable de entorno EPIDEMIC_API_KEY (en desarrollo también del `.env` de la raíz del proyecto, que Git ignora; la plantilla
es `.env.example`). Al leerla se SACA del entorno del proceso: los programas que lanza CineCaptions (Resolve, la IA local, node…) no la heredan.
Nunca se imprime, se anota en el Registro, se guarda en un estado o una configuración, se manda a la interfaz ni a Git: todo lo que sale de aquí
dice solo «configurada» / «no configurada». Solo viaja en la cabecera Authorization hacia BASE (https); las URLs firmadas del CDN se piden SIN ella.

API (developers.epidemicsound.com, spec 0.1.17, rutas /v0): Authorization: Bearer <clave> + `x-partner-user-id` = identificador ANÓNIMO y estable
de este equipo (nunca el nombre ni el correo).

    acceso(preview=False, descarga=False)  prueba SEGURA del nivel real de la cuenta: conexión, autenticación, catálogo (/v0/collections),
                                           búsqueda de SFX y de música; preview/stream y descarga SOLO si se piden (en el plan gratuito
                                           cuentan contra 100 streams y 50 descargas DE POR VIDA); límites (cabeceras RateLimit y X-RateLimit-*)
    buscar_sfx(term) · buscar_musica(term) varios candidatos (quien elige es el director, nunca «el primer resultado»)
    materializar(tipo, asset, query, uso)  UNA descarga por asset: URL de la API → archivo en sound_director/cache/epidemic/{music,sfx,ambience}/
                                           + metadata (provider, asset_id, title, category, query, download_quality, local_path, file_hash,
                                           project_usage, date_downloaded). Si ya hay una copia válida no se vuelve a llamar a la descarga; los
                                           duplicados se controlan por asset_id + file_hash. El original NUNCA se toca: el proceso va a processed/.

Errores (docs/errors): 401 clave inválida → no se reintenta · 403 fuera del plan → esa función queda «no disponible», no se reintenta · 404 no
existe · 406 cortafuegos del CDN → espera ≥ 2 s · 429 / 502 / 503 → `Retry-After` (segundos o fecha HTTP) o 1, 2, 4 s, hasta 3 intentos · 500 una
vez. Nada de esto para GO: quien llama recibe un `Respuesta` con `error` y sigue con procedural / caché / silencio (nunca con los legacy).
Todo esto hace red: SIEMPRE desde un hilo de trabajo, nunca desde el hilo de la interfaz.
"""
import email.utils
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

ENV = 'EPIDEMIC_API_KEY'
BASE = 'https://api.epidemicsound.com'
TIEMPO = 20
INTENTOS = 3
CATEGORIAS = ('music', 'sfx', 'ambience')
_CLAVE = [None]
_NO_DISPONIBLE = set()                  # funciones que dieron 403 en esta sesión (no se vuelven a pedir)


# ------------------------------------------------------------------------------------------------------------------------------ la clave
def _de_dotenv():
    """La clave del `.env` de la raíz del proyecto (solo en desarrollo; Git lo ignora). None si no hay."""
    ruta = Path(__file__).resolve().parent.parent / '.env'
    try:
        for linea in ruta.read_text(encoding='utf-8').splitlines():
            k, _s, v = linea.strip().partition('=')
            if k.strip() == ENV and v.strip():
                return v.strip().strip('"').strip("'")
    except OSError:
        pass
    return None


def _clave():
    v = os.environ.pop(ENV, None)                         # (fuera del entorno: los procesos hijos no la heredan)
    if v and v.strip():
        _CLAVE[0] = v.strip()
    if not _CLAVE[0]:
        _CLAVE[0] = _de_dotenv()
    return _CLAVE[0] or None


def configurada():
    """¿Hay clave? (sin decir nunca cuál)."""
    return _clave() is not None


def _olvidar():
    """(pruebas) Olvida la clave leída."""
    _CLAVE[0] = None
    _NO_DISPONIBLE.clear()


def _usuario():
    """Identificador anónimo y estable de este equipo para `x-partner-user-id` (hash; nunca el nombre ni el correo)."""
    return hashlib.sha256(f'cinecaptions|{uuid.getnode()}|{Path.home().name}'.encode('utf-8')).hexdigest()[:24]


def _sin_clave(texto):
    """Cualquier texto que vaya a salir (errores, informes) sin la clave aunque una respuesta la repitiera."""
    k = _CLAVE[0]
    s = str(texto)
    return s.replace(k, '«clave»') if k else s


# ------------------------------------------------------------------------------------------------------------------------------ peticiones
class Respuesta:
    def __init__(self, status, datos=None, limites=None, error=None, intentos=1):
        self.status, self.datos, self.limites, self.error, self.intentos = status, datos, limites or {}, error, intentos

    @property
    def ok(self):
        return self.status is not None and 200 <= self.status < 300

    def resumen(self):
        return {'status': self.status, 'ok': self.ok, 'error': self.error, 'intentos': self.intentos, 'limites': self.limites}


LIMITES = ('RateLimit', 'RateLimit-Policy', 'X-RateLimit-Reached', 'X-RateLimit-Reset', 'x-user-ratelimit-count', 'x-user-ratelimit-limit',
           'X-User-Rate-Limit-Reset', 'Retry-After')


def _limites(cabeceras):
    return {k: cabeceras.get(k) for k in LIMITES if cabeceras is not None and cabeceras.get(k) is not None}


def _espera(cabeceras, intento):
    """Segundos a esperar: Retry-After (segundos o fecha HTTP) o 1, 2, 4…"""
    ra = cabeceras.get('Retry-After') if cabeceras is not None else None
    if ra:
        try:
            return max(0.0, float(ra))
        except ValueError:
            try:
                return max(0.0, email.utils.parsedate_to_datetime(ra).timestamp() - time.time())
            except Exception:
                pass
    return float(2 ** intento)


def _mensaje(cuerpo):
    try:
        d = json.loads(cuerpo.decode('utf-8'))
        if d.get('errors'):
            return '; '.join(f"{e.get('key')}: {', '.join(e.get('messages') or [])}" for e in d['errors'])
        return str(d.get('message') or '')[:200]
    except Exception:
        return ''


MOTIVO = {401: 'clave inválida o caducada', 403: 'tu plan no incluye esto', 404: 'no existe', 406: 'el cortafuegos del CDN bloqueó la descarga',
          429: 'límite de peticiones alcanzado', 500: 'error del servidor de Epidemic', 502: 'error transitorio', 503: 'servicio no disponible'}


def pedir(ruta, params=None, intentos=INTENTOS, funcion=None, espera_max=30.0):
    """GET a la API (con la clave). Reintenta lo que se puede reintentar; nunca lanza: devuelve una Respuesta."""
    if funcion and funcion in _NO_DISPONIBLE:
        return Respuesta(403, error=f'{MOTIVO[403]} (ya visto en esta sesión)', intentos=0)
    clave = _clave()
    if not clave:
        return Respuesta(None, error='EPIDEMIC_API_KEY no configurada', intentos=0)
    url = BASE.rstrip('/') + ruta + ('?' + urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v is not None}) if params else '')
    cab = {'Authorization': 'Bearer ' + clave, 'Accept': 'application/json', 'x-partner-user-id': _usuario(), 'User-Agent': 'CineCaptions-AI-Sound-Director'}
    ultimo = None
    for intento in range(max(1, intentos)):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=cab), timeout=TIEMPO) as r:
                cuerpo = r.read()
                try:
                    datos = json.loads(cuerpo.decode('utf-8')) if cuerpo else None
                except ValueError:
                    datos = None
                return Respuesta(r.status, datos, _limites(r.headers), intentos=intento + 1)
        except urllib.error.HTTPError as e:
            cuerpo = e.read() if hasattr(e, 'read') else b''
            ultimo = Respuesta(e.code, None, _limites(e.headers), _sin_clave(f"{e.code} {MOTIVO.get(e.code, 'error')}: {_mensaje(cuerpo)}".strip(': ')),
                               intento + 1)
            if e.code == 403 and funcion:
                _NO_DISPONIBLE.add(funcion)
            if e.code in (401, 403, 404, 400):
                return ultimo
            if e.code in (429, 502, 503, 504, 406, 500) and intento + 1 < intentos:
                espera = _espera(e.headers, intento)
                if e.code == 406:
                    espera = max(espera, 2.0 * (intento + 1))
                if e.code == 500 and intento >= 1:
                    return ultimo
                time.sleep(min(espera, espera_max))
                continue
            return ultimo
        except Exception as e:                               # sin red, DNS, tiempo agotado…
            ultimo = Respuesta(None, error=_sin_clave(f'sin conexión: {type(e).__name__}'), intentos=intento + 1)
            if intento + 1 < intentos:
                time.sleep(min(2.0 ** intento, espera_max))
    return ultimo


def bajar_url(url, destino, intentos=INTENTOS):
    """Un archivo de una URL FIRMADA del CDN (sin la clave ni parámetros añadidos: la firma cubre la consulta). (ok, error)"""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_name(destino.name + '.parcial')
    for intento in range(max(1, intentos)):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'CineCaptions-AI-Sound-Director'}), timeout=60) as r, open(tmp, 'wb') as f:
                while True:
                    b = r.read(1 << 16)
                    if not b:
                        break
                    f.write(b)
            tmp.replace(destino)
            return True, None
        except urllib.error.HTTPError as e:
            tmp.unlink(missing_ok=True)
            if e.code == 406 and intento + 1 < intentos:
                time.sleep(max(2.0, _espera(e.headers, intento)))
                continue
            return False, f"{e.code} {MOTIVO.get(e.code, 'error')}" + (' (URL caducada o alterada)' if e.code == 401 else '')
        except Exception as e:
            tmp.unlink(missing_ok=True)
            if intento + 1 < intentos:
                time.sleep(2.0 ** intento)
                continue
            return False, f'sin conexión: {type(e).__name__}'
    return False, 'no se pudo descargar'


# ------------------------------------------------------------------------------------------------------------------------------ catálogo
def _lista(datos, *claves):
    for k in claves:
        if isinstance(datos, dict) and isinstance(datos.get(k), list):
            return datos[k]
    return datos if isinstance(datos, list) else []


def _asset(x, tipo):
    """Lo que el director necesita de un resultado (id, título, duración, categoría, preview solo/descargable…)."""
    if not isinstance(x, dict):
        return None
    dur = x.get('length') or x.get('duration') or x.get('durationInSeconds')
    if isinstance(dur, (int, float)) and dur > 1000:
        dur = dur / 1000.0
    return {'provider': 'epidemic', 'tipo': tipo, 'asset_id': str(x.get('id') or x.get('trackId') or ''), 'title': x.get('title') or x.get('name'),
            'duracion': dur, 'bpm': x.get('bpm'), 'moods': [m.get('name') if isinstance(m, dict) else m for m in (x.get('moods') or [])][:5],
            'genres': [g.get('name') if isinstance(g, dict) else g for g in (x.get('genres') or [])][:5],
            'categoria': (x.get('category') or {}).get('name') if isinstance(x.get('category'), dict) else x.get('category'),
            'solo_preview': x.get('isPreviewOnly'), 'explicit': x.get('isExplicit')}


def buscar_sfx(term, limit=12):
    r = pedir('/v0/sound-effects/search', {'term': str(term)[:500], 'limit': int(limit)}, funcion='sfx_busqueda')
    return r, [a for a in (_asset(x, 'sfx') for x in _lista(r.datos, 'soundEffects', 'tracks', 'items')) if a and a['asset_id']]


def buscar_musica(term, limit=12, **filtros):
    r = pedir('/v0/tracks/search', dict({'term': str(term)[:500], 'limit': int(limit)}, **filtros), funcion='musica_busqueda')
    return r, [a for a in (_asset(x, 'music') for x in _lista(r.datos, 'tracks', 'items')) if a and a['asset_id']]


def url_descarga(tipo, asset_id, quality='normal'):
    """La URL firmada (y cuándo caduca). CUENTA como una descarga en Epidemic: pedirla solo para un asset ya elegido."""
    ruta = f"/v0/{'tracks' if tipo == 'music' else 'sound-effects'}/{urllib.parse.quote(str(asset_id))}/download"
    return pedir(ruta, {'format': 'mp3', 'quality': quality}, funcion=f'descarga_{tipo}')


# ------------------------------------------------------------------------------------------------------------------------------ caché profesional
def carpeta_cache():
    import director_sonido_estado as E
    return E.CARPETA / 'cache' / 'epidemic'


def _indice_ruta():
    return carpeta_cache() / 'indice.json'


def indice():
    import archivos_seguros
    d = archivos_seguros.leer_json(_indice_ruta(), {}, con_respaldo=True)
    return d if isinstance(d, dict) else {}


def _sha(ruta):
    h = hashlib.sha256()
    with open(ruta, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def en_cache(asset_id, quality='normal'):
    """La entrada de la caché de ese asset si su archivo sigue ahí y su huella cuadra (si no, None)."""
    e = indice().get(f'{asset_id}|{quality}')
    if not e or not e.get('local_path') or not Path(e['local_path']).is_file():
        return None
    try:
        return e if _sha(e['local_path']) == e.get('file_hash') else None
    except OSError:
        return None


def materializar(tipo, asset, query='', uso=None, quality='normal'):
    """El archivo LOCAL de un asset ELEGIDO por el director (una sola descarga). Devuelve (entrada | None, motivo). Con copia válida no se llama a
    la API (sirve también sin conexión al reabrir un proyecto). Duplicados: por asset_id y por file_hash."""
    import archivos_seguros
    if tipo not in CATEGORIAS:
        return None, f'tipo desconocido: {tipo}'
    aid = str(asset.get('asset_id') if isinstance(asset, dict) else asset)
    clave_idx = f'{aid}|{quality}'
    ya = en_cache(aid, quality)
    if ya:
        if uso and uso not in (ya.get('project_usage') or []):
            ya = dict(ya, project_usage=list(ya.get('project_usage') or []) + [uso])
            archivos_seguros.mezclar_json(_indice_ruta(), {clave_idx: ya}, indent=1)
        return ya, 'ya estaba en la caché (sin descargar otra vez)'
    r = url_descarga(tipo, aid, quality)
    if not r.ok or not isinstance(r.datos, dict) or not r.datos.get('url'):
        return None, r.error or 'la API no dio una URL de descarga'
    destino = carpeta_cache() / tipo / f'{aid}_{quality}.mp3'
    ok, err = bajar_url(r.datos['url'], destino)
    if not ok:
        return None, err
    h = _sha(destino)
    for k, e in indice().items():                           # el mismo archivo con otro id: se reutiliza el que ya estaba
        if e.get('file_hash') == h and Path(e.get('local_path') or '').is_file() and Path(e['local_path']) != destino:
            destino.unlink(missing_ok=True)
            destino = Path(e['local_path'])
            break
    entrada = {'provider': 'epidemic', 'asset_id': aid, 'title': asset.get('title') if isinstance(asset, dict) else None,
               'category': (asset.get('categoria') if isinstance(asset, dict) else None) or tipo, 'tipo': tipo, 'query': str(query)[:200],
               'download_quality': quality, 'local_path': str(destino), 'file_hash': h, 'project_usage': [uso] if uso else [],
               'date_downloaded': time.strftime('%Y-%m-%d %H:%M:%S'), 'expira_url': r.datos.get('expires')}
    archivos_seguros.mezclar_json(_indice_ruta(), {clave_idx: entrada}, indent=1)
    return entrada, 'descargado una vez y guardado en la caché'


def ruta_procesada(entrada, sufijo='processed'):
    """Dónde va la COPIA procesada (WAV) de un asset de la caché; el original descargado nunca se toca."""
    p = Path(entrada['local_path'])
    return p.parent / 'processed' / f"{p.stem}_{sufijo}.wav"


# ------------------------------------------------------------------------------------------------------------------------------ prueba segura
def acceso(preview=False, descarga=False, term_sfx='whoosh for a fast scene transition', term_musica='calm upbeat background for a vlog'):
    """El nivel REAL de acceso de la cuenta, sin suponer nada. Sin `preview`/`descarga` no gasta streams ni descargas. Nunca incluye la clave."""
    inf = {'configurada': configurada(), 'base': BASE, 'funciones': {}, 'limites': {}, 'nivel': None}
    if not inf['configurada']:
        inf['nivel'] = 'sin clave'
        return inf

    def anotar(nombre, r, extra=None):
        inf['funciones'][nombre] = dict(r.resumen(), **(extra or {}))
        if r.limites:
            inf['limites'] = dict(inf['limites'], **r.limites)
    r = pedir('/v0/collections', {'limit': 5}, intentos=2, funcion='catalogo')
    cols = _lista(r.datos, 'collections', 'items')
    anotar('catalogo', r, {'colecciones': len(cols)})
    inf['conexion'] = r.status is not None
    inf['autenticacion'] = 'ok' if r.ok else ('clave inválida' if r.status == 401 else (r.error or 'sin respuesta'))
    if r.status in (None, 401):
        inf['nivel'] = 'sin conexión' if r.status is None else 'clave inválida'
        return inf
    rs, sfx = buscar_sfx(term_sfx, 8)
    anotar('sfx_busqueda', rs, {'resultados': len(sfx), 'ejemplos': [{k: a[k] for k in ('asset_id', 'title', 'duracion')} for a in sfx[:3]]})
    rm, mus = buscar_musica(term_musica, 8)
    anotar('musica_busqueda', rm, {'resultados': len(mus), 'solo_preview': sum(1 for a in mus if a.get('solo_preview')),
                                   'ejemplos': [{k: a[k] for k in ('asset_id', 'title', 'duracion', 'bpm')} for a in mus[:3]]})
    if preview:
        if sfx:
            rp = pedir(f"/v0/sound-effects/{urllib.parse.quote(sfx[0]['asset_id'])}/preview", funcion='sfx_preview')
            anotar('sfx_preview', rp, {'url': bool(isinstance(rp.datos, dict) and rp.datos.get('url'))})
        if mus:
            rt = pedir(f"/v0/tracks/{urllib.parse.quote(mus[0]['asset_id'])}/stream", funcion='musica_stream')
            anotar('musica_stream', rt, {'url': bool(isinstance(rt.datos, dict) and rt.datos.get('url'))})
    if descarga and sfx:
        entrada, motivo = materializar('sfx', sfx[0], term_sfx, uso='prueba de acceso')
        inf['funciones']['descarga_sfx'] = {'ok': entrada is not None, 'motivo': motivo, 'archivo': bool(entrada), 'bytes': Path(entrada['local_path']).stat().st_size if entrada else 0}
    f = inf['funciones']
    if f.get('catalogo', {}).get('ok') and f.get('sfx_busqueda', {}).get('ok') and f.get('musica_busqueda', {}).get('ok'):
        inf['nivel'] = 'catálogo y búsqueda (música y SFX)'
    elif f.get('sfx_busqueda', {}).get('ok') or f.get('musica_busqueda', {}).get('ok'):
        inf['nivel'] = 'parcial (' + ', '.join(k for k, v in f.items() if v.get('ok')) + ')'
    else:
        inf['nivel'] = 'sin acceso al catálogo (' + str(f.get('catalogo', {}).get('error')) + ')'
    return json.loads(_sin_clave(json.dumps(inf, ensure_ascii=False, default=str)))
