# CineCaptions · By Cinema Productions
# 1_codigo/herramientas_dev/probar_epidemic.py — prueba SEGURA del cliente de Epidemic Sound del AI Sound Director (nunca enseña la clave).
"""
    python probar_epidemic.py                    el cliente contra un servidor FALSO local: 401 / 403 / 406 / 429, reintentos con Retry-After, descarga
                                                 UNA vez a la caché (music/sfx/ambience) con su metadata, duplicados, y que la clave no salga NUNCA
                                                 (ni en pantalla, ni en el Registro, ni en archivos, ni a procesos hijos, ni al CDN)
    python probar_epidemic.py --real             contra TU cuenta (EPIDEMIC_API_KEY en el entorno o en el .env del proyecto): conexión, autenticación,
                                                 catálogo, búsqueda de SFX y de música y límites. No gasta streams ni descargas…
        [--preview]                              …salvo con --preview (1 preview de SFX + 1 stream de música: cuentan para los 100 streams del plan gratuito)
        [--descarga]                             …y --descarga (1 SFX a la caché: cuenta para las 50 descargas del plan gratuito)
    [--salida X]                                 dónde va el informe (por defecto %TEMP%/cc_epidemic); con --real, también la caché de la prueba
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
RESULTADOS = []


def ok(nombre, cond, detalle=''):
    RESULTADOS.append((nombre, bool(cond), str(detalle)))
    print(('  PASA  ' if cond else '  FALLA ') + nombre + (f'  ({detalle})' if detalle else ''))


class Falso(BaseHTTPRequestHandler):
    """Lo justo de la API y del CDN de Epidemic, con fallos a demanda (Falso.modo)."""
    modo = {}
    visitas = []
    MP3 = b'ID3\x03\x00\x00\x00\x00\x00\x00' + b'\xff\xfb\x90\x00' * 400          # (bytes de prueba: la caché no decodifica)
    PISTAS = None                      # resultados de /v0/tracks/search (None = el de siempre)
    SFX = None                         # resultados de /v0/sound-effects/search
    AUDIO = {}                         # {prefijo del asset: bytes de audio de VERDAD} (fase 4 del director: se decodifica y se procesa)

    def log_message(self, *a):
        pass

    def _json(self, code, datos, cab=None):
        cuerpo = json.dumps(datos).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        for k, v in (cab or {}).items():
            self.send_header(k, v)
        self.send_header('Content-Length', str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        u = urlparse(self.path)
        Falso.visitas.append({'ruta': u.path, 'consulta': u.query, 'auth': self.headers.get('Authorization'), 'usuario': self.headers.get('x-partner-user-id')})
        m = Falso.modo.get(u.path)
        if isinstance(m, list) and m:
            m = m.pop(0)
        if u.path.startswith('/cdn/'):
            if 'sig=firma' not in u.query or '&' in u.query.replace('sig=firma&exp=1', ''):
                return self._json(401, {'message': 'firma alterada'})
            if m == 406:
                return self._json(406, {'message': 'bloqueado'})
            self.send_response(200)
            self.send_header('Content-Type', 'audio/mpeg')
            nombre = u.path.split('/')[-1]
            cuerpo = next((b for k, b in Falso.AUDIO.items() if nombre.startswith(k)), None) or (Falso.MP3 + u.path.encode('utf-8'))
            self.send_header('Content-Length', str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)
            return
        if isinstance(m, int):
            if m == 429:
                return self._json(429, {'message': 'Too many requests'}, {'Retry-After': '1', 'X-RateLimit-Reached': 'true'})
            return self._json(m, {'message': f'error {m} (eco: {self.headers.get("Authorization")})'})
        if not (self.headers.get('Authorization') or '').startswith('Bearer '):
            return self._json(401, {'message': 'Unauthorized'})
        lim = {'RateLimit-Policy': '"burst";q=290;w=1, "daily";q=5000;w=86400', 'RateLimit': '"burst";r=289;t=1, "daily";r=4990;t=48213'}
        if u.path == '/v0/collections':
            return self._json(200, {'collections': [{'id': 'c1', 'name': 'Vlog'}, {'id': 'c2', 'name': 'Calm'}]}, lim)
        if u.path == '/v0/sound-effects/search':
            if not parse_qs(u.query).get('term'):
                return self._json(400, {'message': 'Bad Request', 'errors': [{'key': 'term', 'messages': ['required']}]})
            return self._json(200, {'soundEffects': Falso.SFX if Falso.SFX is not None else
                                    [{'id': f'sfx{i}', 'title': f'Designed Whoosh {i}', 'length': 1200 + i} for i in range(3)]}, lim)
        if u.path == '/v0/tracks/search':
            return self._json(200, {'tracks': Falso.PISTAS if Falso.PISTAS is not None else
                                    [{'id': 'trk1', 'title': 'Calm Vlog', 'length': 151, 'bpm': 96, 'isPreviewOnly': True}]}, lim)
        if u.path.endswith('/download'):
            aid = u.path.split('/')[3]
            nombre = 'mismo' if aid in ('sfxA', 'sfxB') else aid
            return self._json(200, {'url': f'http://{self.headers.get("Host")}/cdn/{nombre}.mp3?sig=firma&exp=1', 'expires': '2026-10-22T10:00:00Z'}, lim)
        if u.path.endswith('/preview') or u.path.endswith('/stream'):
            return self._json(200, {'url': f'http://{self.headers.get("Host")}/cdn/prev.m3u8?sig=firma&exp=1'}, lim)
        return self._json(404, {})


def falso():
    srv = ThreadingHTTPServer(('127.0.0.1', 0), Falso)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f'http://127.0.0.1:{srv.server_address[1]}'


def pruebas_falsas(salida):
    import director_sonido_epidemic as EP
    import director_sonido_estado as Es
    import registro
    log = []
    registro.anotar = lambda nivel, m, o='', d='': log.append(str(m))
    Es.CARPETA = Path(salida) / 'sound_director'
    import shutil
    shutil.rmtree(Es.CARPETA, ignore_errors=True)
    srv, base = falso()
    EP.BASE = base
    EP._olvidar()
    os.environ.pop(EP.ENV, None)
    real_dotenv = EP._de_dotenv
    EP._de_dotenv = lambda: None                                     # (que un .env real del proyecto no cuente en estas pruebas)
    print('\n== sin clave ==')
    ok('sin clave: configurada() = False', EP.configurada() is False)
    r = EP.pedir('/v0/collections')
    ok('sin clave: no se hace ninguna petición y se dice por qué', r.status is None and 'no configurada' in r.error and not Falso.visitas, r.error)
    ok('sin clave: acceso() → «sin clave»', EP.acceso()['nivel'] == 'sin clave')
    secreto = 'es_live_PRUEBA_' + 'x' * 24
    os.environ[EP.ENV] = secreto
    print('\n== con clave (servidor falso) ==')
    ok('la clave se lee del entorno', EP.configurada() is True)
    ok('…y sale del entorno del proceso (los programas hijos no la heredan)', EP.ENV not in os.environ)
    hijo = subprocess.run([sys.executable, '-c', f'import os; print(os.environ.get("{EP.ENV}", "NO"))'], capture_output=True, text=True)
    ok('un proceso hijo no la ve', hijo.stdout.strip() == 'NO')
    inf = EP.acceso()
    ok('acceso: catálogo y búsqueda (música y SFX)', inf['nivel'] == 'catálogo y búsqueda (música y SFX)' and inf['funciones']['sfx_busqueda']['resultados'] == 3,
       inf['nivel'])
    ok('acceso: lee los límites (RateLimit / RateLimit-Policy)', 'RateLimit' in inf['limites'] and 'RateLimit-Policy' in inf['limites'], list(inf['limites']))
    ok('acceso: sin --preview ni --descarga no gasta streams ni descargas', not any(v['ruta'].endswith(('/download', '/preview', '/stream')) for v in Falso.visitas))
    ok('la clave va SOLO en Authorization hacia la API', all(v['auth'] == 'Bearer ' + secreto for v in Falso.visitas if not v['ruta'].startswith('/cdn/')))
    ok('x-partner-user-id anónimo y estable (no el nombre)', len({v['usuario'] for v in Falso.visitas}) == 1 and 'CINEMA' not in (Falso.visitas[0]['usuario'] or ''))
    # 401
    Falso.visitas.clear()
    Falso.modo = {'/v0/collections': 401}
    inf = EP.acceso()
    ok('401: «clave inválida», sin reintentar', inf['nivel'] == 'clave inválida' and len(Falso.visitas) == 1)
    ok('401: el mensaje NO repite la clave (aunque el servidor la devuelva)', secreto not in json.dumps(inf, ensure_ascii=False) and '«clave»' in json.dumps(inf, ensure_ascii=False), inf['funciones']['catalogo']['error'])
    # 403 en música (plan sin música): queda no disponible y no se vuelve a pedir
    Falso.modo = {'/v0/tracks/search': 403}
    Falso.visitas.clear()
    inf = EP.acceso()
    ok('403: acceso parcial (solo lo que tu plan permite)', inf['nivel'].startswith('parcial') and inf['funciones']['musica_busqueda']['status'] == 403, inf['nivel'])
    n = len(Falso.visitas)
    r, _m = EP.buscar_musica('otra cosa')
    ok('403: esa función no se vuelve a pedir en la sesión', r.status == 403 and len(Falso.visitas) == n)
    EP._NO_DISPONIBLE.clear()
    # 429 con Retry-After
    Falso.modo = {'/v0/sound-effects/search': [429, 429]}
    t = time.time()
    r, sfx = EP.buscar_sfx('whoosh')
    ok('429: espera el Retry-After y reintenta (3.ª vez bien)', r.ok and r.intentos == 3 and time.time() - t >= 1.9 and len(sfx) == 3, f'{r.intentos} intentos, {time.time() - t:.1f} s')
    Falso.modo = {'/v0/sound-effects/search': [429, 429, 429, 429]}
    r, _s = EP.buscar_sfx('whoosh')
    ok('429 persistente: se rinde con un error claro (sin colgarse)', r.status == 429 and 'límite' in r.error and r.intentos == 3, r.error)
    Falso.modo = {}
    # 400 (sin término)
    r = EP.pedir('/v0/sound-effects/search', {'limit': 3})
    ok('400: el error de validación se explica', r.status == 400 and 'term' in (r.error or ''), r.error)
    # descarga UNA vez a la caché + metadata
    Falso.visitas.clear()
    entrada, motivo = EP.materializar('sfx', {'asset_id': 'sfx1', 'title': 'Designed Whoosh 1'}, 'whoosh rápido', uso='proyecto-1')
    campos = ('provider', 'asset_id', 'title', 'category', 'query', 'download_quality', 'local_path', 'file_hash', 'project_usage', 'date_downloaded')
    ok('descarga: el archivo queda en cache/epidemic/sfx/ con su metadata', entrada and all(k in entrada for k in campos) and Path(entrada['local_path']).is_file()
       and Path(entrada['local_path']).parent == Es.CARPETA / 'cache' / 'epidemic' / 'sfx', motivo)
    cdn = [v for v in Falso.visitas if v['ruta'].startswith('/cdn/')]
    ok('descarga: la URL firmada se pide tal cual y SIN la clave', len(cdn) == 1 and cdn[0]['auth'] is None and cdn[0]['consulta'] == 'sig=firma&exp=1')
    n_api = sum(1 for v in Falso.visitas if v['ruta'].endswith('/download'))
    e2, motivo2 = EP.materializar('sfx', {'asset_id': 'sfx1'}, 'whoosh rápido', uso='proyecto-2')
    ok('segunda vez: NO se vuelve a llamar a la descarga (caché válida)', sum(1 for v in Falso.visitas if v['ruta'].endswith('/download')) == n_api and e2['project_usage'] == ['proyecto-1', 'proyecto-2'],
       motivo2)
    ok('el índice guarda el uso por proyecto', EP.indice()['sfx1|normal']['project_usage'] == ['proyecto-1', 'proyecto-2'])
    a, _ = EP.materializar('sfx', {'asset_id': 'sfxA'}, 'x')
    b, _ = EP.materializar('sfx', {'asset_id': 'sfxB'}, 'x')
    ok('duplicados por file_hash: dos ids con el mismo archivo comparten una copia', a and b and a['file_hash'] == b['file_hash'] and a['local_path'] == b['local_path'])
    procesada = EP.ruta_procesada(entrada)
    ok('las copias procesadas van a processed/ (el original no se toca)', procesada.parent.name == 'processed' and procesada != Path(entrada['local_path']))
    Path(entrada['local_path']).write_bytes(b'roto')
    ok('si la copia local se estropea, deja de valer (huella)', EP.en_cache('sfx1') is None)
    EP.BASE = 'http://127.0.0.1:1'
    ok('sin red: un asset ya materializado se sigue usando', EP.en_cache('sfxA') is not None)
    r = EP.pedir('/v0/collections', intentos=1)
    ok('sin red: error claro, nada se cuelga', r.status is None and 'sin conexión' in r.error, r.error)
    EP.BASE = base
    # 406 del CDN
    Falso.modo = {'/cdn/sfx9.mp3': [406]}
    t = time.time()
    e9, m9 = EP.materializar('ambience', {'asset_id': 'sfx9'}, 'calle')
    ok('406 del CDN: espera ≥ 2 s y reintenta', e9 is not None and time.time() - t >= 1.9 and Path(e9['local_path']).parent.name == 'ambience', m9)
    # la clave no está en ningún archivo ni en el Registro
    textos = [p.read_text(encoding='utf-8', errors='replace') for p in Path(salida).rglob('*') if p.is_file() and p.suffix in ('.json', '.txt', '.log')]
    ok('la clave no aparece en ningún archivo escrito', not any(secreto in t for t in textos), f'{len(textos)} archivos revisados')
    ok('la clave no aparece en el Registro', not any(secreto in m for m in log))
    import director_sonido_musica as MU
    ok('el director ve «Epidemic configurado» sin tocar la clave', MU.proveedores()['epidemic'] is True)
    EP._olvidar()
    EP._de_dotenv = real_dotenv
    srv.shutdown()


def prueba_real(salida, preview, descarga):
    import director_sonido_epidemic as EP
    import director_sonido_estado as Es
    Es.CARPETA = Path(salida) / 'sound_director'
    print('\n== tu cuenta de Epidemic Sound (prueba segura) ==')
    if not EP.configurada():
        print('  EPIDEMIC_API_KEY no está en el entorno de este proceso (ni en el .env del proyecto).')
        return None
    print('  clave: configurada (no se enseña)')
    inf = EP.acceso(preview=preview, descarga=descarga)
    print(json.dumps(inf, ensure_ascii=False, indent=1))
    (Path(salida) / 'epidemic_acceso.json').write_text(json.dumps(inf, ensure_ascii=False, indent=1), encoding='utf-8')
    return inf


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    args = sys.argv[1:]
    salida = Path(args[args.index('--salida') + 1]) if '--salida' in args else Path(tempfile.gettempdir()) / 'cc_epidemic'
    salida.mkdir(parents=True, exist_ok=True)
    if '--real' in args:
        prueba_real(salida, '--preview' in args, '--descarga' in args)
    else:
        pruebas_falsas(salida)
        pasan = sum(1 for _n, b, _d in RESULTADOS if b)
        print(f'\n{pasan}/{len(RESULTADOS)} pruebas pasan')
        sys.stdout.flush()
        os._exit(0 if pasan == len(RESULTADOS) else 1)


if __name__ == '__main__':
    main()
