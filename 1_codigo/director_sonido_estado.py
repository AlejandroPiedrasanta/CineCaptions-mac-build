# CineCaptions · By Cinema Productions
# 1_codigo/director_sonido_estado.py — «AI Sound Director» (v5.34): el estado `sound_design_project` de cada video (lo analizado, decidido y medido).
"""
Un JSON por video en ~/DaVinciSubtitles/sound_director/<huella>.json (SIEMPRE con archivos_seguros) y, al lado, la carpeta <huella>/ con las copias
procesadas (la voz, más adelante música, ambientes y sonidos): los originales nunca se tocan. La huella sale de la ruta, el tamaño y la fecha del archivo:
si el video cambia, el estado viejo no vale y lo procesado se rehace.

    {'version', 'video', 'huella', 'actualizado',
     'tema', 'perfil', 'paleta', 'analisis': {'voz', 'musica', 'ambiente', 'captions', 'motions', 'narrativa'},
     'voice_backend', 'voice_quality_before', 'voice_quality_after', 'voz': {'archivo', 'clave', 'cadena', 'motivo'},
     'ambience_analysis', 'ambience_events', 'music_decision_state',
     'eventos': [], 'locks': {}, 'overrides': {}, 'metricas': {}, 'sound_score': None, 'score_components': {}}

`general()` / `poner_general()` guardan lo que no es de un video: p. ej. que la última colocación dejó AI VOICE en un timeline (para devolver A1
cuando el director se apaga).
"""
import hashlib
import math
import time
from pathlib import Path

CARPETA = Path.home() / 'DaVinciSubtitles' / 'sound_director'
VERSION = 1


def huella(video):
    """16 hex de la ruta absoluta + tamaño + fecha del archivo (otro archivo u otra versión del mismo = otra huella)."""
    p = Path(str(video)).expanduser()
    try:
        st = p.stat()
        extra = f'{st.st_size}:{int(st.st_mtime)}'
    except OSError:
        extra = ''
    try:
        ruta = str(p.resolve())
    except OSError:
        ruta = str(p)
    return hashlib.sha1((ruta.lower() + '|' + extra).encode('utf-8')).hexdigest()[:16]


def carpeta_de(video):
    """Donde van las copias procesadas de ESTE video."""
    return CARPETA / huella(video)


def ruta_de(video):
    return CARPETA / f'{huella(video)}.json'


def nuevo(video):
    return {'version': VERSION, 'video': str(video), 'huella': huella(video), 'actualizado': None,
            'tema': None, 'perfil': None, 'paleta': None, 'analisis': {},
            'voice_backend': None, 'voice_quality_before': None, 'voice_quality_after': None, 'voz': None,
            'ambience_analysis': None, 'ambience_events': [], 'music_decision_state': None,
            'eventos': [], 'locks': {}, 'overrides': {}, 'metricas': {}, 'sound_score': None, 'score_components': {}}


def limpio(x, decimales=4):
    """Lo mismo con tipos de JSON (numpy fuera, NaN/inf → None, floats redondeados)."""
    if isinstance(x, dict):
        return {str(k): limpio(v, decimales) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [limpio(v, decimales) for v in x]
    if isinstance(x, bool) or x is None or isinstance(x, str):
        return x
    if isinstance(x, int):
        return x
    try:
        import numpy as np
        if isinstance(x, np.bool_):
            return bool(x)
        if isinstance(x, np.integer):
            return int(x)
    except Exception:
        pass
    try:
        f = float(x)
    except (TypeError, ValueError):
        return str(x)
    if math.isnan(f) or math.isinf(f):
        return None
    return round(f, decimales)


def cargar(video):
    """El estado de ese video (uno nuevo si no hay, si es de otra versión o si está roto)."""
    import archivos_seguros
    d = archivos_seguros.leer_json(ruta_de(video), None, con_respaldo=True)
    base = nuevo(video)
    if isinstance(d, dict) and d.get('version') == VERSION and d.get('huella') == base['huella']:
        base.update(d)
    return base


def guardar(video, estado):
    """Lo escribe de forma atómica (archivos_seguros) y lo devuelve ya limpio."""
    import archivos_seguros
    estado = limpio(dict(estado))
    estado['version'], estado['huella'], estado['video'] = VERSION, huella(video), str(video)
    estado['actualizado'] = time.strftime('%Y-%m-%d %H:%M:%S')
    archivos_seguros.escribir_json(ruta_de(video), estado, indent=1)
    return estado


def general():
    import archivos_seguros
    d = archivos_seguros.leer_json(CARPETA / 'general.json', {})
    return d if isinstance(d, dict) else {}


def poner_general(**cambios):
    import archivos_seguros
    CARPETA.mkdir(parents=True, exist_ok=True)
    return archivos_seguros.mezclar_json(CARPETA / 'general.json', limpio(cambios))
