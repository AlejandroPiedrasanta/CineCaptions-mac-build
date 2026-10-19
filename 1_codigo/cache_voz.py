# CineCaptions · By Cinema Productions
# 1_codigo/cache_voz.py — caché de transcripciones: el mismo video con el mismo motor e idioma no se vuelve a transcribir.
"""
cache_voz.py  (v5.4.8)
----------------------
Transcribir es lo más lento de GO (modelos de varios GB, minutos en videos largos). Si sueltas OTRA VEZ el mismo video (o repites GO con otro estilo), la
voz ya está: aquí se guarda `~/DaVinciSubtitles/cache_voz/<huella>.json` con las palabras tal como salieron.

La huella mezcla: tamaño, fecha de modificación, los primeros y últimos 2 MB del archivo (no se lee el video entero), el idioma pedido, el motor de voz
y el modelo. Si cambia cualquiera —otro motor, otro idioma, el archivo editado— es otra huella y se transcribe de nuevo. Nada se borra a mano: `limpiar()`
quita lo viejo (90 días) o lo que pase de 200 MB.

    palabras = cache_voz.leer(ruta, idioma, modelo)       # lista de {'word','start','end',…} o None
    cache_voz.guardar(ruta, idioma, modelo, palabras)
"""
import hashlib
import json
import time
from pathlib import Path

VERSION = 'v1'
CARPETA = Path.home() / 'DaVinciSubtitles' / 'cache_voz'
TROZO = 2 * 1024 * 1024
MAX_DIAS = 90
MAX_MB = 200


def _motor():
    try:
        import ajustes_ui
        return str(ajustes_ui.leer_prefs().get('motor_voz') or 'qwen3')
    except Exception:
        return 'qwen3'


_GENERACION = {}


def _generacion(motor):
    """v5.5.17: la GENERACIÓN del motor Qwen (sus requisitos y su script, que viajan con el programa): al mejorar el motor cambia y cada video se
    vuelve a transcribir UNA vez con el nuevo. Antes la huella solo decía «qwen3»: tras el motor 2.0 (Transformers nativo, mucho mejor: «Xela»,
    «FIFA», «Glass Collective») GO seguía sirviendo lo del motor viejo («Shela», «cifas», «Glasgow»)."""
    if motor != 'qwen3':
        return ''
    if motor not in _GENERACION:
        try:
            import motor_voz
            base = motor_voz._base_recursos() / 'motor_qwen'
            h = hashlib.sha1()
            for n in ('requisitos_motor_qwen.txt', 'motor_qwen.py'):
                h.update((base / n).read_bytes())
            _GENERACION[motor] = h.hexdigest()[:10]
        except Exception:
            _GENERACION[motor] = ''
    return _GENERACION[motor]


def huella(ruta, idioma, modelo=''):
    """La huella corta (24 hex) del video + idioma + motor (y su generación) + modelo; None si no se puede leer el archivo."""
    try:
        r = Path(ruta)
        st = r.stat()
        h = hashlib.sha1()
        motor = _motor()
        h.update(f'{VERSION}|{st.st_size}|{st.st_mtime_ns}|{idioma}|{motor}|{modelo}|{_generacion(motor)}'.encode('utf-8'))
        with open(r, 'rb') as f:
            h.update(f.read(TROZO))
            if st.st_size > TROZO * 2:
                f.seek(-TROZO, 2)
                h.update(f.read(TROZO))
        return h.hexdigest()[:24]
    except Exception:
        return None


def _a_json(o):
    try:
        return float(o)
    except Exception:
        return str(o)


def _valida(palabras):
    return (isinstance(palabras, list) and len(palabras) > 0
            and all(isinstance(p, dict) and 'word' in p and 'start' in p and 'end' in p for p in palabras))


def leer(ruta, idioma, modelo=''):
    """Las palabras ya transcritas de ese video, o None."""
    h = huella(ruta, idioma, modelo)
    if h is None:
        return None
    f = CARPETA / f'{h}.json'
    try:
        d = json.loads(f.read_text(encoding='utf-8'))
        if d.get('version') == VERSION and _valida(d.get('palabras')):
            try:
                f.touch()                         # «usado hace poco»: limpiar() quita primero lo que no se usa
            except OSError:
                pass
            return d['palabras']
    except Exception:
        pass
    return None


def guardar(ruta, idioma, modelo, palabras):
    """Guarda la transcripción (si es válida). Nunca lanza: un fallo de disco no puede romper GO."""
    try:
        if not _valida(palabras):
            return False
        palabras = json.loads(json.dumps(palabras, default=_a_json))        # (numpy float32 y similares)
        h = huella(ruta, idioma, modelo)
        if h is None:
            return False
        CARPETA.mkdir(parents=True, exist_ok=True)
        import archivos_seguros
        archivos_seguros.escribir_json(CARPETA / f'{h}.json', {'version': VERSION, 'video': Path(ruta).name, 'idioma': idioma, 'motor': _motor(), 'modelo': modelo,
                                                                'creado': time.time(), 'palabras': palabras})
        limpiar()
        return True
    except Exception:
        return False


def limpiar(max_dias=MAX_DIAS, max_mb=MAX_MB):
    """Quita las transcripciones sin usar en `max_dias` días y, si el total pasa de `max_mb`, las menos usadas. Devuelve cuántas quitó."""
    quitadas = 0
    try:
        archivos = sorted((f for f in CARPETA.glob('*.json')), key=lambda f: f.stat().st_mtime)
        corte = time.time() - max_dias * 86400
        for f in list(archivos):
            if f.stat().st_mtime < corte:
                f.unlink()
                archivos.remove(f)
                quitadas += 1
        total = sum(f.stat().st_size for f in archivos) / 1e6
        while archivos and total > max_mb:
            f = archivos.pop(0)
            total -= f.stat().st_size / 1e6
            f.unlink()
            quitadas += 1
    except Exception:
        pass
    return quitadas


def resumen():
    """(cuántas, MB) para Ajustes."""
    try:
        archivos = list(CARPETA.glob('*.json'))
        return len(archivos), sum(f.stat().st_size for f in archivos) / 1e6
    except Exception:
        return 0, 0.0
