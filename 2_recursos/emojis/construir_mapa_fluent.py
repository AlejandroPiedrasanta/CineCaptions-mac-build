# CineCaptions · By Cinema Productions
# 2_recursos/emojis/construir_mapa_fluent.py — genera fluent_mapa.json: qué emoji del catálogo (id) corresponde a qué PNG 3D del repositorio microsoft/fluentui-emoji.
"""
Uso:   python construir_mapa_fluent.py [lista.json]

Una sola petición a la API de GitHub (la lista de archivos del repositorio, ~3 MB de texto; no baja ninguna imagen) o, si se pasa `lista.json` (el resultado ya guardado), sin red. Casa cada id de
indice.json con la carpeta Fluent de nombre equivalente (sin distinguir mayúsculas ni signos: «smiling_face_with_heart_eyes» = «Smiling face with heart-eyes») y, si el emoji tiene tonos de
piel, usa el «Default». Escribe fluent_mapa.json = {id: «<Carpeta>/3D/<archivo>.png»}; emojis_sets.py lo usa para bajar cada PNG la primera vez que se necesita.
"""
import json
import os
import re
import sys
import urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
URL = 'https://api.github.com/repos/microsoft/fluentui-emoji/git/trees/main?recursive=1'


def _norma(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


def lista_de_archivos(ruta=None):
    if ruta:
        return json.load(open(ruta, encoding='utf-8'))['png3d']
    req = urllib.request.Request(URL, headers={'User-Agent': 'CineCaptions-dev', 'Accept': 'application/vnd.github+json'})
    datos = json.loads(urllib.request.urlopen(req, timeout=90).read().decode('utf-8'))
    return [t['path'] for t in datos.get('tree', []) if t.get('type') == 'blob' and t['path'].startswith('assets/') and '/3D/' in t['path'] and t['path'].endswith('.png')]


def construir(png3d):
    indice = json.load(open(os.path.join(AQUI, 'indice.json'), encoding='utf-8'))
    por_norma = {}
    for ruta in png3d:
        partes = ruta.split('/')                                  # assets/<Nombre>/3D/<archivo>   |   assets/<Nombre>/<Tono>/3D/<archivo>
        if len(partes) == 4:
            stem = re.sub(r'_3d\.png$', '', partes[-1])
        elif len(partes) == 5 and partes[2] == 'Default':
            stem = re.sub(r'_3d_default\.png$', '', partes[-1])
        else:
            continue
        por_norma.setdefault(_norma(stem), '/'.join(partes[1:]))
    mapa = {}
    for e in indice['emojis']:
        r = por_norma.get(_norma(e['id']))
        if r:
            mapa[e['id']] = r
    return mapa, [e['id'] for e in indice['emojis'] if e['id'] not in mapa]


if __name__ == '__main__':
    mapa, faltan = construir(lista_de_archivos(sys.argv[1] if len(sys.argv) > 1 else None))
    with open(os.path.join(AQUI, 'fluent_mapa.json'), 'w', encoding='utf-8') as fh:
        json.dump(mapa, fh, ensure_ascii=False, separators=(',', ':'), sort_keys=True)
    print(f'{len(mapa)} de {len(mapa) + len(faltan)} emojis del catálogo tienen Fluent 3D. Sin él: {len(faltan)} (siguen con el del sistema).')
    print('ejemplos sin Fluent:', faltan[:20])
