# CineCaptions · By Cinema Productions
# 1_codigo/tema.py — temas de la interfaz (superficies, color de resaltado, tamaño) y su traductor de colores.
"""
tema.py
-------
Ajustes > Interfaz: el tema (superficies), el color de resaltado y el tamaño
de la interfaz. Se aplican AL ARRANCAR, antes de crear ninguna ventana:
qt_kit traduce cada color de la casa con traductor() (hoja de estilo,
constantes, QColor de los dibujos), asi que no hay que tocar las ~400
apariciones de colores del codigo. Cambiar de tema = reiniciar el programa
(Ajustes lo hace con un clic).

La traduccion va por familias, mirando el color en HLS:
  * familia del ACENTO (azules con croma alto: botones, enlaces, bordes
    elegidos): se lleva al tono del acento elegido, conservando lo claro u
    oscuro que era respecto al azul original;
  * SUPERFICIES y textos azulados (fondos, tarjetas, bordes, grises): el tema
    les cambia el matiz (Negro profundo: neutros; Grafito: gris calido).
Los colores con significado (roles del editor, verde/ambar/rojo de estado)
no se tocan.
"""
import colorsys
import json
from functools import lru_cache
from pathlib import Path

from i18n import tr

PREFS = Path.home() / 'DaVinciSubtitles' / 'preferencias.json'
BASE_ACENTO = '#0F62FE'

PERFILES = {
    'noche': (tr('CineCaptions Noche'), tr('El azul marino de siempre, con profundidad.')),
    'negro': (tr('Negro profundo'), tr('Negros neutros en capas que realzan el color de resaltado.')),
    'grafito': (tr('Grafito'), tr('Gris carbón cálido, con menos contraste.')),
}
ACENTO_POR_DEFECTO = 'verde'          # v5.22: el verde, de fábrica (el usuario lo pidió; antes el azul)
ACENTOS = {
    'verde': (tr('Verde'), '#22B573'),
    'azul': (tr('Azul CineCaptions'), '#0F62FE'),
    'naranja': (tr('Naranja cine'), '#F5832F'),
    'violeta': (tr('Violeta'), '#8B5CF6'),
    'rosa': (tr('Rosa'), '#E8457E'),
    'cian': (tr('Cian'), '#0EA5C6'),
}
TAMANOS = (90, 100, 110, 125, 150)
LATERAL = {
    'auto': tr('Automática (según el ancho)'),
    'expandida': tr('Siempre expandida'),
    'compacta': tr('Siempre compacta (solo iconos)'),
    'recordar': tr('Recordar último estado'),
}
# colores con significado propio: no siguen al tema
EXCLUIDOS = {'#4589FE', '#F5B84B', '#B388FF', '#6B7A99', '#24D18F', '#FF6B6B', '#E0A030',
             '#62D196', '#FFD166', '#FFB86B', '#00C8FF'}


def leer():
    """{'tema', 'acento', 'acento_personal', 'tamano', 'lateral'} con valores validos."""
    try:
        p = json.loads(PREFS.read_text(encoding='utf-8'))
    except Exception:
        p = {}
    tema = p.get('tema') if p.get('tema') in PERFILES else 'noche'
    acento = p.get('acento') if p.get('acento') in ACENTOS or p.get('acento') == 'personal' else ACENTO_POR_DEFECTO
    personal = p.get('acento_personal') if _es_hex(p.get('acento_personal')) else ACENTOS[ACENTO_POR_DEFECTO][1]
    try:
        tamano = int(p.get('tamano_interfaz') or 100)
    except (TypeError, ValueError):
        tamano = 100
    if tamano not in TAMANOS:
        tamano = 100
    lateral = p.get('lateral_inicio') if p.get('lateral_inicio') in LATERAL else 'auto'
    return {'tema': tema, 'acento': acento, 'acento_personal': personal, 'tamano': tamano,
            'lateral': lateral, 'lateral_ultimo': bool(p.get('lateral_plegado'))}


def color_acento(ajustes=None):
    a = ajustes or leer()
    return a['acento_personal'] if a['acento'] == 'personal' else ACENTOS[a['acento']][1]


def _es_hex(c):
    return isinstance(c, str) and len(c) == 7 and c.startswith('#') and all(
        ch in '0123456789abcdefABCDEF' for ch in c[1:])


def _hls(c):
    return colorsys.rgb_to_hls(int(c[1:3], 16) / 255, int(c[3:5], 16) / 255, int(c[5:7], 16) / 255)


def _hex(h, l, s):
    r, g, b = colorsys.hls_to_rgb(h % 1.0, max(0.0, min(1.0, l)), max(0.0, min(1.0, s)))
    return '#{:02X}{:02X}{:02X}'.format(round(r * 255), round(g * 255), round(b * 255))


def traductor(ajustes=None):
    """Una funcion '#RRGGBB' -> '#RRGGBB', o None si el tema es el de fabrica."""
    a = ajustes or leer()
    acento = color_acento(a).upper()
    if a['tema'] == 'noche' and acento == BASE_ACENTO:
        return None
    hb, lb, sb = _hls(BASE_ACENTO)
    ha, la, sa = _hls(acento)
    tema = a['tema']
    # un color ya traducido no se vuelve a traducir (las constantes del tema
    # pasan otra vez por _color() y por QColor al dibujarse)
    salidas = set()

    def _calcular(cu):
        h, l, s = _hls(cu)
        tono = h * 360
        croma = (1 - abs(2 * l - 1)) * s
        if 195 <= tono <= 235 and croma >= 0.30 and acento != BASE_ACENTO:
            nl = l * la / lb if l <= lb else la + (l - lb) * (1 - la) / (1 - lb)
            return _hex(ha, nl, min(1.0, s * sa / sb))
        if 195 <= tono <= 235 and s > 0.08 and croma < 0.30:
            if tema == 'negro':
                return _hex(h, l * 0.9, s * 0.07)
            if tema == 'grafito':
                return _hex(32 / 360, l * 1.02, s * 0.14)
        return cu

    @lru_cache(maxsize=None)
    def traducir(c):
        cu = c.upper()
        if cu in EXCLUIDOS or cu in salidas or not _es_hex(cu):
            return c
        nuevo = _calcular(cu)
        if nuevo != cu:
            salidas.add(nuevo)
            return nuevo
        return c

    return traducir


def escala(ajustes=None):
    return (ajustes or leer())['tamano'] / 100.0
