# CineCaptions · By Cinema Productions
"""Descarga packs CC0 de sus páginas públicas y crea un catálogo auditable.

Solo desarrollo: python preparar_biblioteca_sonido_libre.py --descargar
No se ejecuta durante el inicio de la aplicación. No requiere cuentas ni claves.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import io
import json
import re
import stat
import sys
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / '1_codigo'))
import director_sonido_recursos_libres as R

DESTINO = RAIZ / '2_recursos' / 'biblioteca_sonido_libre'
MAX_DESCARGA = 300 * 1024 * 1024
MAX_EXTRAIDO = 1024 * 1024 * 1024
MAX_ARCHIVO = 100 * 1024 * 1024
EXT_AUDIO = {'.wav', '.ogg', '.mp3', '.flac', '.aiff', '.aif'}
DOMINIOS = {'kenney.nl', 'opengameart.org', 'www.opengameart.org'}
PACKS = [
    ('kenney_' + p.replace('-', '_'), 'Kenney', 'https://kenney.nl/assets/' + p, 'natural')
    for p in ('interface-sounds', 'impact-sounds', 'ui-audio', 'rpg-audio', 'casino-audio', 'digital-audio', 'sci-fi-sounds')
] + [
    ('rubberduck_100_sfx', 'rubberduck', 'https://opengameart.org/content/100-cc0-sfx', 'natural'),
    ('rubberduck_80_rpg', 'rubberduck', 'https://opengameart.org/content/80-cc0-rpg-sfx', 'natural'),
    ('rubberduck_50_scifi', 'rubberduck', 'https://opengameart.org/content/50-cc0-sci-fi-sfx', 'ciencia_ficcion'),
    ('rubberduck_80_criaturas', 'rubberduck', 'https://opengameart.org/content/80-cc0-creature-sfx', 'criatura'),
    ('unicae_teclado', 'unicaegames', 'https://opengameart.org/content/keyboard-soundpack-1-typing-and-single-keystrokes', 'natural'),
    ('subspace_retro_512', 'SubspaceAudio', 'https://opengameart.org/content/512-sound-effects-8-bit-style', 'retro'),
    ('superpowers_sfx', 'Sparklin Labs', 'https://opengameart.org/content/superpowers-assets-sound-effects', 'retro'),
]


def _url_segura(url):
    u = urllib.parse.urlparse(url)
    if u.scheme != 'https' or u.hostname not in DOMINIOS or u.username or u.password:
        raise ValueError('Origen de descarga fuera de la lista verificada: ' + url)
    return url


def descargar(url, limite=MAX_DESCARGA):
    req = urllib.request.Request(_url_segura(url), headers={'User-Agent': 'CineCaptions-CC0-Library/1.0'})
    with urllib.request.urlopen(req, timeout=90) as respuesta:
        _url_segura(respuesta.url)
        largo = int(respuesta.headers.get('Content-Length') or 0)
        if largo > limite:
            raise ValueError('La descarga supera el límite permitido')
        datos = bytearray()
        while bloque := respuesta.read(1024 * 1024):
            datos.extend(bloque)
            if len(datos) > limite:
                raise ValueError('La descarga supera el límite permitido')
    return bytes(datos)


def obtener_fuente(pack):
    identificador, autor, pagina, estilo = pack
    contenido = descargar(pagina, limite=4 * 1024 * 1024).decode('utf-8', 'replace')
    if 'kenney.nl' in pagina:
        if 'Creative Commons CC0' not in contenido:
            raise ValueError('La página de Kenney no confirma CC0')
    else:
        # Comprueba el enlace de licencia, no la aparición de CC0 en un comentario.
        licencia = re.search(r'field-name-field-art-licenses.*?(?:field-name-|</article>)', contenido, re.S)
        if not licencia or not re.search(r'creativecommons.org/publicdomain/zero/1.0', licencia.group(0)):
            raise ValueError('La ficha del autor no confirma la licencia CC0')
    enlaces = [html.unescape(x) for x in re.findall(r'href=[\"\']([^\"\']+)[\"\']', contenido)]
    zips = sorted(set(urllib.parse.urljoin(pagina, x) for x in enlaces if urllib.parse.urlparse(x).path.lower().endswith('.zip')))
    if not zips:
        raise ValueError('No hay archivos ZIP públicos en la página')
    return contenido, zips


def _miembro_seguro(info):
    nombre = info.filename.replace('\\', '/')
    partes = PurePosixPath(nombre)
    if partes.is_absolute() or '..' in partes.parts or ':' in nombre or '\x00' in nombre:
        raise ValueError('Ruta insegura en ZIP: ' + nombre)
    if stat.S_ISLNK(info.external_attr >> 16):
        raise ValueError('Enlace simbólico no permitido: ' + nombre)
    if info.file_size > MAX_ARCHIVO:
        raise ValueError('Archivo demasiado grande: ' + nombre)
    if info.compress_size and info.file_size / info.compress_size > 1000:
        raise ValueError('Compresión sospechosa: ' + nombre)
    return nombre


def _nombre_portable(nombre):
    # Conserva la procedencia en el manifiesto; usa nombres ASCII en Resolve.
    import unicodedata
    texto = unicodedata.normalize('NFKD', nombre).encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'[^A-Za-z0-9_.-]+', '_', texto).strip('._')[:120] or 'audio'


def preparar(seleccion=None):
    DESTINO.mkdir(parents=True, exist_ok=True)
    manifiesto_ruta = DESTINO / 'manifiesto.json'
    anterior = json.loads(manifiesto_ruta.read_text('utf-8')) if manifiesto_ruta.exists() else {}
    archivos = [a for a in anterior.get('archivos', []) if (DESTINO / a['ruta']).is_file()]
    packs = list(anterior.get('packs', []))
    vistos = {a['sha256']: a['ruta'] for a in archivos}
    errores = []
    elegidos = [p for p in PACKS if not seleccion or p[0] in seleccion]
    for pack in elegidos:
        identificador, autor, pagina, estilo = pack
        if any(p['id'] == identificador for p in packs):
            print(identificador + ': ya preparado', flush=True)
            continue
        try:
            pagina_texto, zips = obtener_fuente(pack)
            carpeta = DESTINO / identificador
            carpeta.mkdir(parents=True, exist_ok=True)
            licencias, origenes, nuevos, duplicados = [], [], [], []
            for url in zips:
                datos = descargar(url)
                origenes.append({'url': url, 'sha256': hashlib.sha256(datos).hexdigest(), 'bytes': len(datos)})
                with zipfile.ZipFile(io.BytesIO(datos)) as z:
                    if len(z.infolist()) > 20000 or sum(x.file_size for x in z.infolist()) > MAX_EXTRAIDO:
                        raise ValueError('Contenido ZIP excesivo')
                    for info in z.infolist():
                        nombre = _miembro_seguro(info)
                        if info.is_dir():
                            continue
                        sufijo = Path(nombre).suffix.lower()
                        es_licencia = sufijo in {'.txt', '.md'} and any(x in Path(nombre).name.lower() for x in ('license', 'licence', 'readme', 'cc0'))
                        if sufijo not in EXT_AUDIO and not es_licencia:
                            continue
                        audio = z.read(info)
                        if es_licencia:
                            destino_lic = carpeta / ('licencia_' + _nombre_portable(Path(nombre).name))
                            destino_lic.write_bytes(audio)
                            licencias.append(str(destino_lic.relative_to(DESTINO)).replace('\\', '/'))
                            continue
                        sha = hashlib.sha256(audio).hexdigest()
                        if sha in vistos:
                            duplicados.append({'original': nombre, 'igual_a': vistos[sha], 'sha256': sha})
                            continue
                        # Un mismo sonido distribuido en varios formatos no incrementa el conteo.
                        identidad = re.sub(r'(^|/)(wav|ogg|mp3|flac)(/|$)', '/', nombre.lower())
                        identidad = str(PurePosixPath(identidad).with_suffix(''))
                        if any(x.get('_identidad') == identidad for x in nuevos):
                            continue
                        ruta = carpeta / (_nombre_portable(Path(nombre).stem) + '_' + sha[:8] + sufijo)
                        ruta.write_bytes(audio)
                        relativo = ruta.relative_to(DESTINO).as_posix()
                        semantica = R.clasificar(nombre, identificador, estilo)
                        entrada = {'ruta': relativo, 'pack': identificador, 'autor': autor, 'origen': pagina,
                                   'licencia': 'CC0-1.0', 'licencia_url': R.LICENCIA_URL,
                                   'original': nombre, 'sha256': sha, 'bytes': len(audio), **semantica, '_identidad': identidad}
                        nuevos.append(entrada)
                        vistos[sha] = relativo
            for x in nuevos:
                x.pop('_identidad', None)
            archivos.extend(nuevos)
            # Guarda evidencia de licencia legible sin incluir HTML activo.
            evidencia = {'pagina': pagina, 'licencia': 'CC0-1.0', 'licencia_url': R.LICENCIA_URL,
                         'fecha_utc': datetime.now(timezone.utc).isoformat(),
                         'pagina_sha256': hashlib.sha256(pagina_texto.encode()).hexdigest()}
            (carpeta / 'origen_licencia.json').write_text(json.dumps(evidencia, ensure_ascii=False, indent=2), 'utf-8')
            packs.append({'id': identificador, 'autor': autor, 'pagina': pagina, 'licencia': 'CC0-1.0',
                          'licencia_url': R.LICENCIA_URL, 'descargas': origenes, 'archivos': len(nuevos),
                          'licencias_incluidas': licencias, 'duplicados_omitidos': duplicados,
                          'verificado_utc': evidencia['fecha_utc']})
            guardar(manifiesto_ruta, archivos, packs)
            print(f'{identificador}: {len(nuevos)} audios únicos, {len(duplicados)} duplicados omitidos', flush=True)
        except Exception as exc:
            errores.append({'pack': identificador, 'error': str(exc)})
            print(f'{identificador}: ERROR {exc}', flush=True)
    guardar(manifiesto_ruta, archivos, packs, errores)
    print(json.dumps({'audios': len(archivos), 'packs': len(packs), 'bytes': sum(x['bytes'] for x in archivos), 'errores': errores}, ensure_ascii=False), flush=True)
    return 1 if errores else 0


def guardar(ruta, archivos, packs, errores=None):
    # Es catálogo de recursos distribuido, nunca preferencias ni estado del usuario.
    datos = {'version': 1, 'licencia': 'CC0-1.0', 'licencia_url': R.LICENCIA_URL,
             'creado_utc': datetime.now(timezone.utc).isoformat(), 'packs': packs,
             'total_archivos': len(archivos), 'bytes_audio': sum(x['bytes'] for x in archivos),
             'archivos': archivos, 'errores': errores or []}
    temporal = ruta.with_suffix('.tmp')
    temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    temporal.replace(ruta)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--descargar', action='store_true')
    parser.add_argument('--pack', action='append')
    args = parser.parse_args()
    if args.descargar:
        raise SystemExit(preparar(args.pack))
    print('\n'.join(f'{p[0]} · {p[2]}' for p in PACKS))
