# CineCaptions · By Cinema Productions
# 1_codigo/vocabulario.py — v5.5.17: el vocabulario del usuario para la voz: los nombres que corrige en Creativo (lugares, marcas, personas,
# grupos) se aprenden, guían a Qwen3-ASR (contexto) y a Whisper (hotwords) y cambian solos las variantes ya conocidas («Shela» → «Xela»).
"""
    aprender_par(antes, despues)    al corregir una palabra en Creativo («Editar palabra»); solo nombres propios, siglas y marcas
    contexto(extra=None)            el texto para el motor de voz (los términos más usados), '' si no hay nada
    huella_contexto(texto)          8 hex para la caché de voz (otro vocabulario = otra transcripción)
    aplicar(palabras)               (palabras, cambios): las variantes aprendidas, cambiadas por su término (mismos tiempos)
    unificar(palabras)              (palabras, cambios): un nombre propio escrito de dos formas que suenan igual («Xela?» / «Shela»), a una

Medido con PRUEBA ESPAÑOL (Qwen3-ASR 1.7B): sin contexto «Shela», «vibras», «envíácelo»; con el vocabulario «Xela», «Vibrass», «envíaselo».
El archivo vive en ~/DaVinciSubtitles/vocabulario.json (se escribe con archivos_seguros).
"""
import hashlib
import re
import threading
import time
import unicodedata
from pathlib import Path

RUTA = Path.home() / 'DaVinciSubtitles' / 'vocabulario.json'
MAX_TERMINOS = 300
MAX_CONTEXTO = 1200                 # caracteres (el «system prompt» de Qwen3-ASR: corto y concreto)
_LOCK = threading.Lock()
_SIGNOS = '¿¡.,;:!?"\'«»()[]…“”'


def _sin_tildes(t):
    t = unicodedata.normalize('NFD', str(t))
    return ''.join(c for c in t if unicodedata.category(c) != 'Mn')


def _limpio(t):
    return str(t or '').strip().strip(_SIGNOS).strip()


def plano(t):
    return re.sub(r'[^a-z0-9 ]', '', _sin_tildes(_limpio(t)).lower()).strip()


def clave_fonetica(t):
    """Cómo SUENA en español (para casar variantes de un mismo nombre): «Shela» = «Xela», «Bibras» = «Vibras», «Kasa» = «Casa»."""
    s = plano(t).replace(' ', '')
    for a, b in (('sh', 'x'), ('ch', 'c'), ('ll', 'y'), ('qu', 'k'), ('gu', 'g'), ('ph', 'f'), ('ck', 'k')):
        s = s.replace(a, b)
    s = re.sub(r'c(?=[ei])', 's', s)
    s = re.sub(r'g(?=[ei])', 'j', s)
    s = s.replace('c', 'k').replace('z', 's').replace('v', 'b').replace('w', 'u').replace('h', '')
    s = re.sub(r'(.)\1+', r'\1', s)                    # letras dobles
    return s


def _es_termino(t):
    """Nombre propio, sigla o marca: lleva alguna mayúscula o cifras con letras («Xela», «FIFA», «iPhone», «DJ», «U2»)."""
    t = _limpio(t)
    return len(t) >= 2 and (any(c.isupper() for c in t) or (any(c.isdigit() for c in t) and any(c.isalpha() for c in t)))


def _leer():
    try:
        import json
        d = json.loads(RUTA.read_text(encoding='utf-8'))
        if isinstance(d, dict) and isinstance(d.get('terminos'), dict):
            return d
    except Exception:
        pass
    return {'version': 1, 'terminos': {}}


def _escribir(d):
    try:
        import archivos_seguros
        RUTA.parent.mkdir(parents=True, exist_ok=True)
        archivos_seguros.escribir_json(RUTA, d)
        return True
    except Exception:
        return False


def aprender_par(antes, despues):
    """El usuario cambió `antes` por `despues`: si `despues` es un nombre propio/sigla/marca (no un simple acento o mayúscula), se aprende."""
    a, d = _limpio(antes), _limpio(despues)
    if not d or not _es_termino(d) or plano(a) == plano(d) or len(d) > 40:
        return False
    with _LOCK:
        datos = _leer()
        t = datos['terminos'].setdefault(d, {'veces': 0, 'de': [], 'ultimo': 0})
        t['veces'] = int(t.get('veces') or 0) + 1
        if a and plano(a) and plano(a) not in t['de']:
            t['de'] = (list(t.get('de') or []) + [plano(a)])[-12:]
        t['ultimo'] = time.time()
        if len(datos['terminos']) > MAX_TERMINOS:          # los menos usados y más viejos, fuera
            orden = sorted(datos['terminos'].items(), key=lambda kv: (kv[1].get('veces', 0), kv[1].get('ultimo', 0)))
            for k, _v in orden[:len(datos['terminos']) - MAX_TERMINOS]:
                datos['terminos'].pop(k, None)
        return _escribir(datos)


def terminos():
    """Los términos aprendidos, los más usados y recientes primero."""
    with _LOCK:
        datos = _leer()
    return [k for k, _v in sorted(datos['terminos'].items(), key=lambda kv: (-int(kv[1].get('veces') or 0), -float(kv[1].get('ultimo') or 0)))]


def contexto(extra=None):
    """El vocabulario para el motor de voz: «Xela, FIFA, Glass Collective, …» (los más usados primero), o ''."""
    vistos, out, largo = set(), [], 0
    for t in list(extra or []) + terminos():
        t = _limpio(t)
        if not t or plano(t) in vistos:
            continue
        if largo + len(t) + 2 > MAX_CONTEXTO:
            break
        vistos.add(plano(t))
        out.append(t)
        largo += len(t) + 2
    return ', '.join(out)


def huella_contexto(texto):
    return hashlib.sha1(str(texto or '').encode('utf-8')).hexdigest()[:8] if texto else ''


def _con_signos(original, nuevo):
    """`nuevo` con los signos de alrededor de `original` («¿Shela?» → «¿Xela?»)."""
    m = re.match(r'^([' + re.escape(_SIGNOS) + r']*)(.*?)([' + re.escape(_SIGNOS) + r']*)$', str(original))
    return f'{m.group(1)}{nuevo}{m.group(3)}' if m else nuevo


def aplicar(palabras):
    """Las variantes que el usuario ya corrigió alguna vez, cambiadas por su término (una palabra por una palabra; los tiempos no cambian)."""
    with _LOCK:
        datos = _leer()
    mapa = {}
    for termino, info in datos['terminos'].items():
        if ' ' in _limpio(termino):
            continue                                       # (un término de dos palabras no cabe en una palabra con su tiempo)
        for v in info.get('de') or []:
            if v and ' ' not in v:
                mapa.setdefault(v, termino)
    if not mapa:
        return palabras, 0
    out, cambios = [], 0
    for p in palabras:
        w = str(p.get('word') or '')
        t = mapa.get(plano(w))
        if t and plano(t) != plano(w):
            p = dict(p, word=_con_signos(w.strip(), t))
            cambios += 1
        out.append(p)
    return out, cambios


def unificar(palabras):
    """Un nombre propio que sale escrito de dos formas que SUENAN igual en el mismo video («Xela?» al principio y «Shela» al final): todas a
    la del vocabulario si la hay; si no, a la más repetida (con empate, la primera que se dijo)."""
    grupos, propio = {}, set()
    for i, p in enumerate(palabras):
        w = _limpio(p.get('word'))
        if not w or not w[0].isupper() or len(w) < 3:
            continue
        k = clave_fonetica(w)
        if len(k) >= 3:
            grupos.setdefault(k, []).append(i)
            antes = str(palabras[i - 1].get('word') or '').strip() if i else ''
            if antes and not re.search(r'[.!?…]$', antes):
                propio.add(k)                              # (en mayúscula A MITAD de frase: un nombre propio, no el inicio de una oración)
    conocidos = {plano(t): t for t in terminos()}
    out = [dict(p) for p in palabras]
    cambios = 0
    for k, idx in grupos.items():
        if k not in propio:
            continue
        formas = {}
        for i in idx:
            formas.setdefault(plano(out[i]['word']), []).append(i)
        if len(formas) < 2:
            continue
        elegida = next((conocidos[f] for f in formas if f in conocidos), None)
        if elegida is None:
            f, lista = max(formas.items(), key=lambda kv: (len(kv[1]), -kv[1][0]))
            elegida = _limpio(out[lista[0]]['word'])
        for i in idx:
            if plano(out[i]['word']) != plano(elegida):
                out[i]['word'] = _con_signos(str(out[i]['word']).strip(), elegida)
                cambios += 1
    return out, cambios
