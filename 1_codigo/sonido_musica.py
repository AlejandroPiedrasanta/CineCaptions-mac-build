# CineCaptions · By Cinema Productions
# 1_codigo/sonido_musica.py — MÚSICA de la biblioteca del autor (Desktop\SFX\02_MUSICA) para la página Sonido (v5.48). Mismo criterio que
# la skill «sonorizar-sfx» (~/.claude/skills/sonorizar-sfx/scripts/musica.py): mantener MOODS y puntuar() iguales en los dos.
"""
    preparar(ctx, filas, lib, carpeta)  3 opciones (de carpetas distintas) horneadas en WAV; la 1.ª queda elegida
    plan(musica)                        [evento 'AI MUSIC'] de la opción elegida ([] = sin música)
    elegir(video, i)                    la página cambia de opción (None = sin música); queda pendiente de «Aplicar a Resolve»

Cómo elige: carpetas por el ánimo (palabras del video, «Fiesta o mar»; si nada encaja, las que más usan los creadores: lo-fi, reggae chill,
corporativa, house) → en cada pista el mejor ARRANQUE en un compás: cortes y golpes A/B del video en el beat (45 %), energía pareja (25 %),
que no sea una intro muda (20 %), que cierre en compás (10 %). Nivel: −6 dB bajo la voz MEDIDO después de un ducking suave (−4 dB al
hablar); el usuario pidió así la música (a −20 y −11 no se oía). Las pistas de Kevin MacLeod (CC BY 4.0) llevan su crédito.
Medidas de cada pista: la caché de la skill si existe (librosa); si no, bpm.py y la energía por pulso, en caché propia.
"""
import hashlib
import json
import os
import re
import time
from pathlib import Path

import numpy as np

SR = 48000
BAJO_VOZ_DB = 6.0
DUCK_DB = -4.0
SIN_VOZ_DB = -20.0
EXT = ('.wav', '.mp3', '.m4a', '.flac')
PREF_MUSICA = 'sonido_musica'
CACHE_SKILL = Path.home() / '.sonorizar-sfx' / 'cache' / 'musica'
CACHE_PROPIA = Path.home() / 'DaVinciSubtitles' / 'musica_biblioteca_medidas.json'
MOODS = {  # carpeta → palabras que la piden (iguales a la skill)
    '05_FIESTA': ('fiesta', 'festival', 'concierto', 'dj', 'discoteca', 'club', 'baile', 'evento nocturno', 'música en vivo'),
    '03_DEPORTE': ('deporte', 'gimnasio', 'gym', 'fútbol', 'futbol', 'entren', 'acción', 'energétic', 'gamer', 'torneo'),
    '02_MOTIVADORA': ('motiv', 'inspir', 'emprend', 'marca personal', 'testimonio', 'juvenil', 'positivo', 'alegre', 'dinámico'),
    '01_EPICA': ('épic', 'epic', 'cine', 'drone', 'paisaje', 'boda', 'lanzamiento', 'superación', 'trailer'),
    '04_MEDITACION': ('calma', 'relaj', 'spa', 'yoga', 'bienestar', 'naturaleza', 'inmobiliaria', 'tranquil', 'lujo'),
    '06_CUMPLEANOS_INFANTIL': ('niño', 'niña', 'infantil', 'cumpleaños', 'piñata'),
    '07_CORPORATIVA_POP': ('marca', 'servicio', 'clínica', 'clinica', 'dental', 'tutorial', 'producto', 'profesional', 'brillante'),
    '08_LUJO_JAZZ_LOUNGE': ('lujo', 'elegan', 'inmobiliaria', 'propiedad', 'casa', 'hotel', 'restaurante', 'sofistic', 'interior'),
    '09_FUNK_GROOVE': ('ritmo', 'groove', 'antes y después', 'moda', 'auto', 'estilo', 'actitud'),
    '10_ELECTRONICA_HOUSE': ('recorrido', 'propiedad', 'tecnolog', 'moderno', 'evento', 'dinámico', 'marketing', 'cortes rápidos'),
    '11_LATINA': ('latino', 'verano', 'comida', 'gastronom', 'tropical', 'fiesta latina'),
    '12_AFRO_WORLD': ('afro', 'cálido', 'calido', 'energétic', 'tribal', 'percusión'),
    '13_REGGAE_CHILL': ('playa', 'mar', 'verano', 'relajado', 'surf', 'lifestyle'),
    '14_HIPHOP_BEAT': ('actitud', 'marca personal', 'tips', 'consejo', 'urbano', 'calle', 'beat'),
    '15_LOFI_CHILL': ('tutorial', 'rutina', 'un día', 'paso a paso', 'estudio', 'trabajo', 'tranquil', 'café'),
    '16_PIANO_EMOTIVA': ('historia', 'testimonio', 'emoci', 'familia', 'gracias', 'mensaje', 'recuerdo'),
    '17_ACUSTICA_FOLK': ('jardín', 'jardin', 'naturaleza', 'campo', 'cálido', 'cercan', 'artesan'),
    '18_SYNTHWAVE_RETRO': ('retro', 'neón', 'neon', 'noche', 'auto', 'tecnolog', 'gamer'),
}
DE_CREADORES = ('15_LOFI_CHILL', '13_REGGAE_CHILL', '07_CORPORATIVA_POP', '10_ELECTRONICA_HOUSE')   # lo que más usan (70 videos)
NOMBRE_CARPETA = {k: k.split('_', 1)[1].replace('_', ' ').capitalize() for k in MOODS}
MARCAS_POOL = ('whoosh', 'swoosh', 'impacto', 'riser', 'glitch', 'flash')   # golpes que un editor pega al beat


def _sk():
    import sonido_skill
    return sonido_skill


def activa(prefs=None):
    return (prefs if prefs is not None else _sk()._prefs()).get(PREF_MUSICA, True) is not False


# ---------------------------------------------------------------------------------------------------- medir pistas
def _de_la_skill(ruta):
    st = os.stat(ruta)
    clave = hashlib.sha1(f'{os.path.abspath(ruta)}|{st.st_size}|{int(st.st_mtime)}'.encode()).hexdigest()[:16]
    try:
        return json.loads((CACHE_SKILL / f'{clave}.json').read_text(encoding='utf-8'))
    except Exception:
        return None


def medir(ruta, cache=None):
    """{dur, bpm, beats, downbeats, energia_db (por beat)}."""
    m = _de_la_skill(ruta)
    if m:
        return m
    import archivos_seguros
    import bpm
    cache = cache if cache is not None else (archivos_seguros.leer_json(CACHE_PROPIA, None) or {})
    st = os.stat(ruta)
    h = hashlib.sha1(f'{os.path.abspath(ruta)}|{st.st_size}|{st.st_mtime_ns}'.encode()).hexdigest()[:16]
    if h in cache:
        return cache[h]
    y = bpm._decodificar(ruta, max_s=900)
    info = bpm.detectar_de_audio(y)
    if not info:
        return None
    dur = len(y) / bpm.TASA
    beats = np.asarray(bpm.golpes_hasta(info, dur), float)
    v = int(0.1 * bpm.TASA)
    e = np.array([np.sqrt(np.mean(y[int(b * bpm.TASA):int(b * bpm.TASA) + v] ** 2) + 1e-12) for b in beats])
    fase = int(np.argmax([e[k::4].mean() if e[k::4].size else 0 for k in range(4)])) if beats.size >= 8 else 0
    m = {'dur': round(dur, 3), 'bpm': info['bpm'], 'beats': [round(float(b), 3) for b in beats],
         'downbeats': [round(float(b), 3) for b in beats[fase::4]], 'energia_db': [round(float(20 * np.log10(x)), 2) for x in e]}
    cache[h] = m
    archivos_seguros.escribir_json(CACHE_PROPIA, cache)
    return m


def puntuar(m, dur, marcas, tol=0.05):
    """Mejor arranque (en un downbeat) de la pista para un video de dur s → (puntaje, ini, detalle). Igual que la skill."""
    beats = np.asarray(m['beats'])
    e = np.asarray(m['energia_db'])
    if beats.size < 16 or m['dur'] < dur * 0.6:
        return None
    mejor = None
    for ini in m['downbeats']:
        if ini + dur > m['dur'] + 0.5:
            break
        dentro = (beats >= ini) & (beats <= ini + dur)
        if dentro.sum() < 8:
            continue
        rel = beats[dentro] - ini
        en_beat = sum(1 for x in marcas if np.min(np.abs(rel - x)) <= tol) / max(1, len(marcas)) if marcas else 0.0
        ed = e[dentro]
        pareja = 1.0 - min(1.0, float(np.std(ed)) / 12.0)
        nivel = min(1.0, max(0.0, (float(np.median(ed)) + 40) / 25))
        db = np.asarray(m['downbeats'])
        cierre = 1.0 - min(1.0, float(np.min(np.abs(db - (ini + dur)))) / 1.0) if db.size else 0.0
        s = 0.45 * en_beat + 0.25 * pareja + 0.2 * nivel + 0.1 * cierre
        if not mejor or s > mejor[0]:
            mejor = (round(s, 3), round(float(ini), 3), {'en_beat': round(en_beat, 2), 'pareja': round(pareja, 2),
                                                         'nivel': round(nivel, 2), 'cierre': round(cierre, 2)})
    return mejor


# ---------------------------------------------------------------------------------------------------- elegir
def carpetas_para(ctx, prefs=None, lib=None):
    """Hasta 5 carpetas: las del ánimo del video primero, luego las que más usan los creadores."""
    prefs = prefs if prefs is not None else _sk()._prefs()
    texto = ' '.join(str(p.get('word', p.get('texto', ''))) for p in ctx.get('palabras') or []).lower() + ' ' + str(ctx.get('pack') or '').lower()
    puntos = {c: sum(texto.count(w) for w in ws) for c, ws in MOODS.items()}
    orden = [c for c, p in sorted(puntos.items(), key=lambda x: -x[1]) if p > 0][:3]
    if prefs.get(_sk().PREF_FIESTA):
        orden = ['05_FIESTA', '13_REGGAE_CHILL'] + orden
    base = Path(lib or _sk().biblioteca()) / '02_MUSICA'
    out = []
    for c in orden + list(DE_CREADORES):
        if c not in out and (base / c).is_dir() and any(f.suffix.lower() in EXT for f in (base / c).iterdir()):
            out.append(c)
    return out[:5], puntos


def duracion(ctx, filas=()):
    rec = ctx.get('recorte') or {}
    if rec.get('segmentos'):
        return round(sum(float(b) - float(a) for a, b in rec['segmentos']), 3)
    try:
        import av
        with av.open(str(ctx.get('video'))) as c:
            d = float(c.duration or 0) / 1e6
        if d > 1:
            return round(d, 3)
    except Exception:
        pass
    return max([float(p.get('end') or 0) + 1.0 for p in ctx.get('palabras') or []] + [float(f['segundo']) + 1.0 for f in filas] + [5.0])


def credito(ruta):
    """Texto de crédito obligatorio (CC BY) o None."""
    ruta = Path(ruta)
    if 'Kevin MacLeod' not in ruta.stem:
        return None
    titulo = ruta.stem.split(' - ')[-1].strip()
    try:
        for bloque in re.split(r'\n\s*\n', (ruta.parent / 'CREDITOS.txt').read_text(encoding='utf-8-sig')):
            if bloque.strip().startswith(f'"{titulo}"'):
                return bloque.strip()
    except Exception:
        pass
    return (f'"{titulo}" Kevin MacLeod (incompetech.com)\nLicensed under Creative Commons: By Attribution 4.0 License\n'
            'http://creativecommons.org/licenses/by/4.0/')


def candidatos(ctx, filas, lib, dur, n=3, prefs=None):
    """Las n mejores pistas, cada una de una carpeta distinta."""
    carpetas, _ = carpetas_para(ctx, prefs, lib)
    marcas = sorted({round(float(t), 3) for t in ctx.get('cortes') or []} |
                    {round(float(f['segundo']), 3) for f in filas if f.get('pool') in MARCAS_POOL})
    import archivos_seguros
    cache = archivos_seguros.leer_json(CACHE_PROPIA, None) or {}
    mejores = {}
    for c in carpetas:
        for ruta in sorted((Path(lib) / '02_MUSICA' / c).iterdir()):
            if ruta.suffix.lower() not in EXT:
                continue
            try:
                m = medir(ruta, cache)
                p = puntuar(m, dur, marcas) if m else None
            except Exception:
                p = None
            if p and (c not in mejores or p[0] > mejores[c]['puntaje']):
                mejores[c] = {'pista': ruta.relative_to(lib).as_posix(), 'carpeta': c, 'titulo': ruta.stem.split(' - ', 1)[-1],
                              'puntaje': p[0], 'ini': p[1], 'bpm': m['bpm'], 'detalle': p[2], 'credito': credito(ruta)}
    return sorted(mejores.values(), key=lambda x: -x['puntaje'])[:n]


# ---------------------------------------------------------------------------------------------------- hornear
def nivel_voz(ctx):
    """dB RMS con puerta de la voz del video (None si no hay palabras)."""
    if not ctx.get('palabras'):
        return None
    import sfx_rules
    try:
        x = _sk().leer_audio(ctx.get('video'), 16000)
        return float(sfx_rules.nivel_de_audio(x.T, 16000)[0]) if x.shape[1] else None
    except Exception:
        return None


def hornear(cand, lib, dur, palabras, voz_db, destino):
    """El tramo [ini, ini+dur] con fundidos, ducking suave y su nivel dentro del WAV (Resolve ignora el volumen de clip por script)."""
    import ducking
    import sfx_rules
    S = _sk()
    x = S.leer_audio(Path(lib) / cand['pista'])
    i0, n = int(cand['ini'] * SR), int(dur * SR)
    seg = x[:, i0:i0 + n]
    if seg.shape[1] < n:
        seg = np.pad(seg, ((0, 0), (0, n - seg.shape[1])))
    fi, fo = int(0.5 * SR), int(min(1.5, max(0.8, dur * 0.06)) * SR)
    seg[:, :fi] *= np.linspace(0.0, 1.0, fi, dtype=np.float32)
    seg[:, -fo:] *= np.linspace(1.0, 0.0, fo, dtype=np.float32)
    if voz_db is not None and palabras:
        curva = ducking.curva_de_ganancia(ducking.intervalos_de_voz(palabras), dur, db_baja=DUCK_DB)
        seg *= np.interp(np.arange(n) / SR, np.arange(len(curva)) / float(ducking.PASO), curva).astype(np.float32)
        objetivo, como = voz_db - BAJO_VOZ_DB, f'−{BAJO_VOZ_DB:g} dB bajo la voz + baja {abs(DUCK_DB):g} dB al hablar'
    else:
        objetivo, como = SIN_VOZ_DB, 'sin voz: fondo a −20 dB'
    rms, pico = sfx_rules.nivel_de_audio(seg.T, SR)
    g = min(objetivo - rms, -1.0 - pico)                          # el pico nunca pasa de −1 dBFS
    seg *= 10 ** (g / 20)
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    S._escribir_wav(destino, seg)
    return como


def preparar(ctx, filas, lib, carpeta, prefs=None, n=3):
    """{'candidatos': [...con 'wav' y 'nivel'], 'elegida': 0|None, 'dur'}. Nunca lanza: sin música si algo falla."""
    if not activa(prefs):
        return {'candidatos': [], 'elegida': None, 'apagada': True}
    try:
        dur = duracion(ctx, filas)
        cands = candidatos(ctx, filas, lib, dur, n, prefs)
        voz = nivel_voz(ctx)
        for i, c in enumerate(cands):
            h = hashlib.sha1(f"{c['pista']}|{c['ini']}|{dur}|{voz}".encode()).hexdigest()[:10]
            c['wav'] = str(Path(carpeta) / f'musica_{i}_{h}.wav')
            c['nivel'] = hornear(c, lib, dur, ctx.get('palabras') or [], voz, c['wav'])
        return {'candidatos': cands, 'elegida': 0 if cands else None, 'dur': dur}
    except Exception:
        try:
            import registro
            registro.excepcion(origen=_sk().ORIGEN)
        except Exception:
            pass
        return {'candidatos': [], 'elegida': None}


def plan(musica):
    m = musica or {}
    i, cands = m.get('elegida'), m.get('candidatos') or []
    if i is None or not 0 <= i < len(cands) or not Path(cands[i].get('wav') or '').is_file():
        return []
    c = cands[i]
    return [{'tipo': 'musica', 'pista': 'AI MUSIC', 'ini': 0.0, 'dur': round(float(m.get('dur') or 0), 3), 'archivo': c['wav'],
             'asset': f"AI MUSIC · {c['titulo']}"[:80],
             'ai': {'id': 'musica', 'tipo': 'musica', 'origen': _sk().ORIGEN, 'fuente': c['pista'], 'clave': 'musica', 'credito': c.get('credito')}}]


def elegir(video, i):
    """La página cambia de opción (None = sin música). (ok, texto)."""
    import director_sonido_estado as E
    estado = E.cargar(video)
    m = estado.get('sonido_musica') or {}
    cands = m.get('candidatos') or []
    if i is not None and not 0 <= i < len(cands):
        return False, 'Esa opción ya no está.'
    m['elegida'] = i
    estado['sonido_musica'], estado['music_plan'], estado['pendiente_resolve'] = m, plan(m), True
    estado.setdefault('sonido_skill', {})['fecha'] = time.strftime('%Y-%m-%d %H:%M:%S')
    E.guardar(video, estado)
    if i is None:
        return True, 'Sin música · pendiente de «Aplicar a Resolve».'
    return True, f"Música: {cands[i]['titulo']} · pendiente de «Aplicar a Resolve»."
