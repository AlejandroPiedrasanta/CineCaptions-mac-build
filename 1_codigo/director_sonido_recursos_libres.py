# CineCaptions · By Cinema Productions
"""Catálogo portable de audio CC0. Sin red ni descargas durante la búsqueda.

El manifiesto mantiene el origen, la licencia y SHA-256 de cada recurso.
Los sonidos de objetos/animales/retro se reservan para escenas explícitas:
no se convierten en acentos genéricos simplemente por tener un impacto.
"""
from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
from functools import lru_cache
from pathlib import Path

LICENCIA_URL = 'https://creativecommons.org/publicdomain/zero/1.0/'


def raiz():
    """Localiza los recursos en fuente, PyInstaller y despliegues portables."""
    bases = [Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))]
    if getattr(sys, 'frozen', False):
        bases.extend((Path(sys.executable).parent, Path(sys.executable).parent.parent))
    bases.append(Path(__file__).resolve().parent.parent)
    candidatos = [b / '2_recursos' / 'biblioteca_sonido_libre' for b in bases]
    return next((p for p in candidatos if (p / 'manifiesto.json').is_file()), candidatos[0])


def _texto(texto):
    texto = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', str(texto))
    texto = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('ascii').lower()
    return re.sub(r'[^a-z0-9]+', ' ', texto).strip()


GRUPOS = {
    'whoosh': ('whoosh', 'swoosh', 'swish', 'sweep', 'swipe', 'woosh', 'swing'),
    'riser': ('riser', 'rise', 'swell', 'uplift', 'build', 'reverse'),
    'trazo': ('pencil', 'pen', 'writing', 'write', 'scribble', 'marker', 'chalk', 'keyboard', 'typing', 'keystroke'),
    'tonal': ('bell', 'chime', 'ping', 'sparkle', 'tone', 'notification', 'positive', 'success'),
    'ui': ('click', 'tap', 'button', 'switch', 'select', 'beep', 'blip', 'interface', 'menu', 'tick', 'pop'),
    'golpe': ('impact', 'hit', 'slam', 'thud', 'punch', 'boom', 'explosion', 'bang'),
    'ambiente': ('ambient', 'ambience', 'wind', 'rain', 'forest', 'river', 'stream', 'ocean', 'wave', 'traffic', 'crowd', 'fire'),
    'foley': ('footstep', 'step', 'door', 'wood', 'metal', 'glass', 'cloth', 'paper', 'water', 'card', 'dice', 'chip', 'stone', 'key'),
}
OBJETOS = ('door', 'wood', 'metal', 'glass', 'footstep', 'step', 'punch', 'gun', 'laser', 'sword', 'coin', 'card', 'dice', 'chip',
           'water', 'paper', 'machine', 'engine', 'monster', 'creature', 'animal', 'toilet', 'weapon', 'shoot', 'splat', 'pot')
SINONIMOS = {'pasos': 'footstep step', 'puerta': 'door', 'agua': 'water splash', 'papel': 'paper', 'teclado': 'keyboard typing',
             'bosque': 'forest nature', 'lluvia': 'rain', 'viento': 'wind', 'mar': 'ocean wave', 'calle': 'street traffic',
             'ciudad': 'city traffic', 'campana': 'bell', 'metal': 'metal', 'madera': 'wood', 'vidrio': 'glass',
             'naturaleza': 'nature forest birds', 'interfaz': 'interface click', 'transicion': 'whoosh transition',
             'retro': 'retro', 'videojuego': 'retro game', 'ciencia ficcion': 'scifi laser space'}


def clasificar(nombre, pack='', estilo='natural'):
    """Metadatos semánticos por nombre original; conservadores con objetos."""
    texto = _texto(nombre)
    tokens = set(texto.split())
    etiquetas = sorted({x for claves in GRUPOS.values() for x in claves if x in tokens})
    categorias = [cat for cat, claves in GRUPOS.items() if tokens.intersection(claves)]
    if 'kenney_interface' in pack or 'kenney_ui' in pack:
        categorias = list(dict.fromkeys(categorias + ['ui']))
    if 'teclado' in pack:
        categorias = list(dict.fromkeys(['trazo'] + categorias))
    if 'scifi' in pack or 'sci_fi' in pack:
        estilo = 'ciencia_ficcion'
    if 'criaturas' in pack:
        estilo = 'criatura'
    objetos = [x for x in OBJETOS if x in tokens]
    return {'cat': categorias[0] if categorias else 'foley', 'categorias': categorias or ['foley'],
            'etiquetas': etiquetas, 'estilo': estilo, 'objetos': objetos,
            'generico': not objetos and estilo not in ('retro', 'criatura', 'ciencia_ficcion')}


@lru_cache(maxsize=4)
def _cargar(ruta, fecha, tamano):
    try:
        datos = json.loads(Path(ruta).read_text('utf-8'))
        return datos if isinstance(datos, dict) and datos.get('version') == 1 else {}
    except (OSError, ValueError):
        return {}


def manifiesto():
    p = raiz() / 'manifiesto.json'
    try:
        st = p.stat()
        return _cargar(str(p), st.st_mtime_ns, st.st_size)
    except OSError:
        return {}


def entradas():
    """Entradas con rutas existentes y licencia CC0 explícita, para el índice común."""
    base = raiz().resolve()
    salida = []
    for entrada in manifiesto().get('archivos', []):
        if not isinstance(entrada, dict) or entrada.get('licencia') != 'CC0-1.0':
            continue
        p = (base / str(entrada.get('ruta', ''))).resolve()
        if not p.is_relative_to(base) or not p.is_file():
            continue
        salida.append({**entrada, 'ruta': str(p), 'modo': None, 'tono': None, 'fuente': 'biblioteca_cc0'})
    return salida


def resumen():
    lista = entradas()
    categorias = {}
    for a in lista:
        categorias[a['cat']] = categorias.get(a['cat'], 0) + 1
    return {'total': len(lista), 'packs': len(manifiesto().get('packs', [])), 'categorias': categorias,
            'licencia': 'CC0-1.0', 'carpeta': str(raiz()), 'bytes': sum(a.get('bytes', 0) for a in lista)}


def buscar(contexto='', cat=None, n=60, permitir_estilizados=False):
    """Busca objetos concretos o acentos genéricos; nunca selecciona por azar."""
    contexto = _texto(contexto)
    expandido = contexto + ' ' + ' '.join(v for k, v in SINONIMOS.items() if k in contexto)
    tokens = set(expandido.split())
    coincidencias = []
    for a in entradas():
        if cat and cat not in a.get('categorias', [a.get('cat')]):
            continue
        if a.get('estilo') == 'retro' and not permitir_estilizados and not tokens.intersection({'retro', 'game', 'videojuego', '8bit'}):
            continue
        if a.get('estilo') in ('criatura', 'ciencia_ficcion') and not permitir_estilizados and not tokens.intersection({'creature', 'monster', 'scifi', 'laser', 'space', 'fantasy', 'criatura', 'monstruo'}):
            continue
        palabras = set(_texto(a.get('original', '')).split()) | set(a.get('etiquetas', []))
        aciertos = len(tokens.intersection(palabras))
        if a.get('objetos') and not tokens.intersection(a['objetos']):
            continue
        if contexto and not aciertos:
            continue
        if not contexto and not a.get('generico'):
            continue
        coincidencias.append((aciertos, a))
    coincidencias.sort(key=lambda par: (-par[0], par[1]['pack'], par[1]['ruta']))
    return [a for _, a in coincidencias[:max(0, int(n))]]


def candidatos(cat, contexto='', n=60):
    return [a['ruta'] for a in buscar(contexto=contexto, cat=cat, n=n)]
