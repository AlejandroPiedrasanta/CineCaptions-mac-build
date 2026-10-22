# CineCaptions · By Cinema Productions
# 1_codigo/director_sonido_capas.py — «AI Sound Director», FASE 4: la MÚSICA y el AMBIENTE (pistas AI MUSIC y AI AMBIENCE).
"""
musica(analisis, ctx, controles, carpeta, nivel_voz_db)    → {'estado', 'por_que', 'candidatos', 'elegido', 'plan', 'tramos'}
ambiente(analisis, ctx, controles, carpeta, nivel_voz_db)  → {'escenas', 'plan', 'resumen'}

MÚSICA (estados del plan): sin música pedida → NO_MUSIC_REQUIRED · el video ya la trae mezclada → KEEP_EXISTING (no se separa ni se pone otra
encima: dos músicas chocan) · hace falta (análisis o el control «Música») y hay proveedor AUTORIZADO → ADD_NEW evaluando VARIOS candidatos (MUSIC FIT:
energía/BPM, duración, mood y género contra la paleta, sin explícitas ni solo-preview), UNA descarga a la caché profesional, copia procesada: bucle
con fundido cruzado si es corta, fundidos de entrada/salida, hueco de EQ donde vive la voz (1–4 kHz) y DUCKING natural por frases (baja con la voz,
respira en las pausas ≥ 0,6 s), nivel relativo a la voz dentro del archivo · v5.37: sin Epidemic (o si nada de Epidemic encaja), una CAMA de score
de la biblioteca del autor (pads/drones de sus colecciones de Film Score, director_sonido_biblioteca.camas: modo mayor si el video es luminoso, menor si
es sobrio) con el mismo proceso y 2 dB más baja (un pad tapa más que una canción) · sin nada que encaje → NO_MUSIC_REQUIRED. Nunca la música vieja.

AMBIENTE: por escena (director_sonido_ambiente): lo que se conserva/limpia/reduce del ORIGINAL ya lo trató la voz (fase 2); lo que se AÑADE
(ADD_SUBTLE_AMBIENCE) sale SOLO de grabaciones profesionales autorizadas (nunca sintetizado ni legacy): Epidemic o, v5.37, las grabaciones de
ambiente de la biblioteca del autor que son de ESE entorno (director_sonido_biblioteca.ambientes); bucle con fundidos, paso alto, hueco en la banda
de la voz, muy por debajo de ella y un poco más bajo cuando habla. Sin grabación de ese entorno → LEAVE_SILENT. Escenas seguidas del mismo entorno =
un tramo.

Todo en streaming por trozos (un video de una hora no carga una hora de audio en memoria). El control del usuario («Música»/«Ambiente»: sin, suave…)
manda sobre la sugerencia de la IA.
"""
import hashlib
import time
from pathlib import Path

import numpy as np

SR = 48000
TROZO_S = 8.0
ENERGIA = {'poco': 0.25, 'medio': 0.5, 'mucho': 0.8}
BPM_OBJETIVO = ((0.35, (68, 96)), (0.65, (88, 118)), (1.01, (108, 138)))      # energía → BPM que encaja
TONAL_A_TERMINO = {'cinemático': 'cinematic', 'digital moderno': 'electronic modern', 'cálido acústico': 'warm acoustic', 'sintético brillante': 'bright synth',
                   'interfaz suave': 'minimal corporate', 'limpio (tecleo)': 'minimal clean', 'neutro': ''}
MUSICA_BAJO_VOZ_DB = {'poco': -19.0, 'medio': -15.0, 'mucho': -12.0, None: -16.0}          # la cama, bajo la voz activa (antes del ducking de −6 dB)
AMBIENTE_BAJO_VOZ_DB = {'poco': -32.0, 'medio': -27.0, 'mucho': -23.0, None: -28.0}
TERMINO_AMBIENTE = {'INTERIOR': 'room tone interior quiet', 'QUIET_INTERIOR': 'quiet room tone', 'ROOM': 'room tone', 'OFFICE': 'office ambience quiet',
                    'STUDIO': 'studio room tone', 'STREET': 'street ambience city', 'CITY': 'city ambience distant', 'OUTDOOR': 'outdoor ambience',
                    'NATURE': 'nature ambience birds', 'FOREST': 'forest ambience', 'PARK': 'park ambience', 'CROWD': 'crowd ambience murmur',
                    'CAFE': 'cafe ambience', 'EVENT': 'event crowd ambience', 'WIND': 'wind ambience soft', 'WATER': 'water stream ambience',
                    'TRAFFIC': 'traffic ambience distant'}
NUNCA_MUSICA = ('vocal', 'vocals', 'lyrics', 'rap', 'karaoke', 'christmas', 'horror', 'national anthem')


# ------------------------------------------------------------------------------------------------------------------------------ utilidades
def _rms_db(x):
    x = np.asarray(x, np.float64)
    return 20 * np.log10(np.sqrt(np.mean(x * x)) + 1e-12)


def _leer(ruta, max_s=None):
    """El archivo entero (o hasta max_s) a 48 kHz estéreo float32."""
    import director_sonido_medir as M
    trozos, total = [], 0
    for t in M.trozos(str(ruta), canales=2):
        t = np.asarray(t, np.float32)
        if t.shape[0] == 1:
            t = np.vstack((t, t))
        trozos.append(t[:2])
        total += t.shape[1]
        if max_s and total >= max_s * SR:
            break
    return np.concatenate(trozos, axis=1) if trozos else None


def _rms_tras_eq(x, eq, max_s=30.0):
    """El nivel (dB RMS) de `x` tal como sonará DESPUÉS de su EQ (un paso alto se come los graves de un room tone: medir antes engaña)."""
    import director_sonido_medir as M
    trozo = x[:, :int(min(x.shape[1], max_s * SR))]
    if not eq:
        return _rms_db(trozo)
    G = M.Grafo(list(eq), 2)
    y = np.concatenate([G.empujar(trozo[:, i:i + SR * 4]) for i in range(0, trozo.shape[1], SR * 4)] + [G.terminar()], axis=1)
    return _rms_db(y)


def _bucleable(x, xf_s=2.0):
    """La pista lista para repetirse sin corte: su cola se funde con su cabeza (fundido de igual potencia)."""
    k = int(min(xf_s * SR, x.shape[1] // 4))
    if k < 64:
        return x
    a = np.sin(np.linspace(0, np.pi / 2, k)) ** 2
    y = x[:, :-k].copy()
    y[:, :k] = x[:, :k] * a + x[:, -k:] * (1 - a)
    return y


def _tramos_voz(palabras, hueco=0.6):
    out = []
    for p in palabras or []:
        a, b = float(p.get('start') or 0.0), float(p.get('end') or 0.0)
        if out and a - out[-1][1] <= hueco:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def _ducking(n_total, tramos, abajo_db, ataque_s=0.12, suelta_s=0.45, tasa=200):
    """La curva de ganancia (dB, a `tasa` Hz) que baja `abajo_db` mientras se habla y respira en las pausas: ataque rápido, suelta lenta."""
    m = int(np.ceil(n_total / SR * tasa)) + 2
    objetivo = np.zeros(m)
    for a, b in tramos:
        objetivo[int(max(0, a - 0.08) * tasa):int((b + 0.15) * tasa) + 1] = abajo_db
    g = np.zeros(m)
    ka, ks = 1 - np.exp(-1.0 / (ataque_s * tasa)), 1 - np.exp(-1.0 / (suelta_s * tasa))
    v = 0.0
    for i in range(m):
        k = ka if objetivo[i] < v else ks
        v += (objetivo[i] - v) * k
        g[i] = v
    return g, tasa


def _escribir_capa(destino, fuente, n_total, nivel_db, ducking, fundido_in=1.5, fundido_out=3.0, eq=(), ini_s=0.0):
    """Escribe la capa de `n_total` muestras repitiendo `fuente` (bucleable), con fundidos, EQ (filtros de ffmpeg) y la curva de ducking, en
    streaming. `nivel_db` = ganancia ya calculada. Devuelve la ruta."""
    import director_sonido_medir as M
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix('.tmp.wav')
    W = M.EscritorWav(tmp, 2)
    G = M.Grafo(list(eq), 2) if eq else None
    g_curva, tasa = ducking if ducking is not None else (None, 1)
    L = fuente.shape[1]
    paso = int(TROZO_S * SR)
    k_in, k_out = int(fundido_in * SR), int(fundido_out * SR)
    escritas = 0
    try:
        for i0 in range(0, n_total, paso):
            i1 = min(n_total, i0 + paso)
            idx = (np.arange(i0, i1) + int(ini_s * SR)) % L
            x = fuente[:, idx] * (10 ** (nivel_db / 20.0))
            t = np.arange(i0, i1)
            env = np.ones(i1 - i0)
            if k_in:
                env *= np.clip(t / max(1, k_in), 0, 1)
            if k_out:
                env *= np.clip((n_total - t) / max(1, k_out), 0, 1)
            if g_curva is not None:
                env *= 10 ** (np.interp(t / SR * tasa, np.arange(len(g_curva)), g_curva) / 20.0)
            x = (x * env).astype(np.float32)
            if G is not None:
                x = G.empujar(x)
            if x.shape[1]:
                W.escribir(np.clip(x, -0.89, 0.89))
                escritas += x.shape[1]
        if G is not None:
            resto = G.terminar()
            if resto.shape[1]:
                W.escribir(np.clip(resto[:, :max(0, n_total - escritas)], -0.89, 0.89))
                escritas += min(resto.shape[1], max(0, n_total - escritas))
        if escritas < n_total:
            W.escribir(np.zeros((2, n_total - escritas), np.float32))
    finally:
        W.cerrar()
    tmp.replace(destino)
    return destino


def _clave(*partes):
    return hashlib.sha1('|'.join(str(p) for p in partes).encode('utf-8')).hexdigest()[:12]


# ------------------------------------------------------------------------------------------------------------------------------ música
def _energia(analisis, controles):
    c = (controles or {}).get('musica')
    if c in ENERGIA:
        return ENERGIA[c], f'pediste música «{c}»'
    return float(((analisis.get('paleta') or {}).get('valores') or {}).get('energia_musica', 0.5)), 'la energía de la paleta del tema'


def _consulta_musica(analisis, energia):
    tonal = str(((analisis.get('perfil') or {}).get('etiquetas') or {}).get('tonal') or '')
    base = 'calm minimal background' if energia < 0.35 else ('light upbeat background' if energia < 0.65 else 'energetic upbeat background beat')
    tono = ((analisis.get('perfil_ia') or {}).get('tono') or '')
    extra = {'elegante': 'elegant', 'inspirador': 'inspiring', 'divertido': 'playful', 'serio': 'serious', 'tecnico': 'tech'}.get(tono, '')
    return ' '.join(x for x in (TONAL_A_TERMINO.get(tonal, ''), extra, base, 'instrumental no vocals') if x)


def music_fit(c, energia, dur):
    """MUSIC FIT 0–1 con sus partes (energía/BPM, duración, mood, sin voces): nunca el primer resultado."""
    lo, hi = next(r for e, r in BPM_OBJETIVO if energia < e)
    bpm = c.get('bpm')
    if bpm:
        e_fit = 1.0 if lo <= bpm <= hi else float(np.exp(-min(abs(bpm - lo), abs(bpm - hi)) / 18.0))
    else:
        e_fit = 0.6
    d = float(c.get('duracion') or 0.0)
    d_fit = 1.0 if d >= dur else (0.85 if d >= 45 else (0.6 if d >= 20 else 0.2))           # (lo corto se repite con fundido; muy corto, no)
    titulo = ' '.join([str(c.get('title') or '')] + [str(m) for m in c.get('moods') or []] + [str(g) for g in c.get('genres') or []]).lower()
    calma, alegria = ('calm', 'chill', 'relax', 'soft', 'ambient', 'peaceful'), ('upbeat', 'happy', 'energetic', 'uplifting', 'driving', 'epic')
    m_fit = 0.5 + 0.25 * (any(w in titulo for w in calma) == (energia < 0.4)) + 0.25 * (any(w in titulo for w in alegria) == (energia >= 0.6))
    penal = 1.0 if any(w in titulo for w in NUNCA_MUSICA) or c.get('explicit') else 0.0
    total = 0.4 * e_fit + 0.25 * d_fit + 0.35 * m_fit - penal
    return round(float(total), 3), {'energia_bpm': round(e_fit, 2), 'duracion': round(d_fit, 2), 'mood': round(m_fit, 2), 'penalizacion': penal}


def musica(analisis, ctx, controles, carpeta, nivel_voz_db):
    """La decisión de la música de ESTE video y, si se añade, su copia procesada (ver el docstring del módulo)."""
    import director_sonido_epidemic as EP
    mu = analisis.get('musica') or {}
    sug = mu.get('estado_sugerido') or {}
    c = (controles or {}).get('musica')
    dur = float((analisis.get('voz') or {}).get('duracion') or 0.0)
    if c == 'nada':
        return {'estado': 'NO_MUSIC_REQUIRED', 'por_que': 'pediste sin música', 'plan': [], 'tramos': []}
    if (mu.get('en_la_fuente') or {}).get('presente'):
        return {'estado': 'KEEP_EXISTING', 'por_que': 'el video ya trae música mezclada con la voz: se conserva (no se separa ni se pone otra encima)',
                'plan': [], 'tramos': [(0.0, dur)]}
    quiere = c in ENERGIA or sug.get('estado') == 'ADD_NEW' or sug.get('deseado') == 'ADD_NEW'
    if not quiere:
        return {'estado': 'NO_MUSIC_REQUIRED', 'por_que': sug.get('por_que') or 'el video no la necesita', 'plan': [], 'tramos': []}
    if not EP.configurada():
        return _musica_del_autor(analisis, ctx, controles, carpeta, nivel_voz_db, 'sin Epidemic (EPIDEMIC_API_KEY)')
    energia, de_donde = _energia(analisis, controles)
    consulta = _consulta_musica(analisis, energia)
    r, cands = EP.buscar_musica(consulta, limit=12)
    if not r.ok:
        return {'estado': 'NO_MUSIC_REQUIRED', 'deseado': 'ADD_NEW', 'plan': [], 'tramos': [], 'por_que': f'el proveedor no respondió: {r.error}'}
    ranking = []
    for cnd in cands:
        if cnd.get('solo_preview'):
            ranking.append((-1.0, cnd, {'rechazado': 'tu cuenta solo permite escucharla (preview), no usarla'}))
            continue
        pts, partes = music_fit(cnd, energia, dur)
        ranking.append((pts, cnd, partes))
    ranking.sort(key=lambda t: -t[0])
    tabla = [{'title': c_.get('title'), 'asset_id': c_.get('asset_id'), 'bpm': c_.get('bpm'), 'duracion': c_.get('duracion'), 'music_fit': p, 'partes': d}
             for p, c_, d in ranking[:6]]
    mejor = next(((p, c_, d) for p, c_, d in ranking if p >= 0.45), None)
    if mejor is None:
        local = _musica_del_autor(analisis, ctx, controles, carpeta, nivel_voz_db, f"ninguna de las {len(ranking)} de Epidemic encaja (consulta «{consulta}»)")
        if local.get('estado') == 'ADD_NEW':
            return local
        return {'estado': 'NO_MUSIC_REQUIRED', 'deseado': 'ADD_NEW', 'plan': [], 'tramos': [], 'candidatos': tabla,
                'por_que': f"ninguna de las {len(ranking)} candidatas encaja de verdad (consulta «{consulta}»): mejor sin música"}
    pts, elegido, partes = mejor
    entrada, motivo = EP.materializar('music', elegido, query=consulta, uso=str(ctx.get('video') or ''))
    if entrada is None:
        return {'estado': 'NO_MUSIC_REQUIRED', 'deseado': 'ADD_NEW', 'plan': [], 'tramos': [], 'candidatos': tabla, 'por_que': f'no se pudo descargar: {motivo}'}
    src = _leer(entrada['local_path'], max_s=600)
    if src is None or src.shape[1] < SR * 5:
        return {'estado': 'NO_MUSIC_REQUIRED', 'deseado': 'ADD_NEW', 'plan': [], 'tramos': [], 'candidatos': tabla, 'por_que': 'el archivo no se pudo leer'}
    fuente = _bucleable(src) if src.shape[1] < dur * SR else src
    c_nivel = c if c in ENERGIA else None
    objetivo = float(nivel_voz_db) + MUSICA_BAJO_VOZ_DB[c_nivel]
    eq = (('equalizer', 'f=2500:t=q:w=1.2:g=-4'), ('equalizer', 'f=350:t=q:w=1:g=-1.5'))
    ganancia = objetivo - _rms_tras_eq(src, eq)
    n = int(round(dur * SR))
    duck = _ducking(n, _tramos_voz(ctx.get('palabras')), -6.0)
    destino = Path(carpeta) / 'musica' / f"AI_MUSIC_{entrada['asset_id']}_{_clave(entrada['file_hash'], n, round(objetivo, 1), c_nivel)}.wav"
    if not destino.is_file():
        _escribir_capa(destino, fuente, n, ganancia, duck, eq=eq)
    ev = {'tipo': 'musica', 'pista': 'AI MUSIC', 'ini': 0.0, 'dur': round(dur, 3), 'archivo': str(destino), 'asset': f"AI MUSIC · {entrada.get('title')}",
          'ai': {'id': 'musica', 'tipo': 'musica', 'origen': 'musica', 'fuente': 'Epidemic Sound (caché profesional)', 'clave': 'musica'}}
    return {'estado': 'ADD_NEW', 'plan': [ev], 'tramos': [(0.0, dur)], 'candidatos': tabla, 'elegido': {'title': entrada.get('title'),
            'asset_id': entrada.get('asset_id'), 'music_fit': pts, 'partes': partes},
            'por_que': f"«{entrada.get('title')}» ({elegido.get('bpm') or '?'} BPM, music fit {pts:.2f}) entre {len(ranking)} candidatas; energía por "
                       f"{de_donde}; {motivo}; bajo la voz con ducking por frases"}


def _brillo(analisis):
    try:
        return float(((analisis.get('paleta') or {}).get('valores') or {}).get('brillo', 0.5))
    except (TypeError, ValueError):
        return 0.5


def _musica_del_autor(analisis, ctx, controles, carpeta, nivel_voz_db, antes):
    """La cama de score de la biblioteca del autor: pads/drones del modo del video que pasan el Quality Gate; entre los mejores (a 0,05 del primero),
    uno por video (dos videos no llevan siempre la misma). `antes`: por qué no viene de Epidemic (para el porqué)."""
    import director_sonido_biblioteca as B
    import director_sonido_fuentes as F
    dur = float((analisis.get('voz') or {}).get('duracion') or 0.0)
    brillo = _brillo(analisis)
    modo = 'mayor' if brillo >= 0.45 else 'menor'
    energia, de_donde = _energia(analisis, controles)
    try:
        cands = B.camas(brillo)
    except Exception:
        cands = []
    if not cands:
        return {'estado': 'NO_MUSIC_REQUIRED', 'deseado': 'ADD_NEW', 'plan': [], 'tramos': [],
                'por_que': f'le iría bien música, pero {antes} y tu biblioteca no tiene camas de score: mejor sin música que con una mediocre'}
    ranking = []
    for a in cands:
        q = F.calidad(a['ruta'], None)
        if q['score'] < F.UMBRAL:
            ranking.append((-1.0, a, {'rechazado': q['motivos']}))
            continue
        w = F._palabras(a['ruta'])
        mueve = any(F._tiene(w, x) for x in ('movement', 'strings', 'string', 'orchestra', 'radiance', 'sunrise', 'summer', 'goated', 'horizon'))
        e_fit = 1.0 - abs((0.75 if mueve else 0.35) - energia)
        m_fit = 1.0 if a.get('modo') == modo else 0.7
        pts = round(0.4 * q['score'] / 100 + 0.35 * m_fit + 0.25 * e_fit, 3)
        ranking.append((pts, a, {'quality': q['score'], 'mood_fit': m_fit, 'energy_fit': round(e_fit, 2)}))
    ranking.sort(key=lambda t: -t[0])
    tabla = [{'title': Path(a['ruta']).stem, 'asset_id': 'autor', 'bpm': None, 'duracion': None, 'music_fit': p, 'partes': d} for p, a, d in ranking[:6]]
    buenos = [t for t in ranking if t[0] >= max(0.45, ranking[0][0] - 0.05)]
    if not buenos:
        return {'estado': 'NO_MUSIC_REQUIRED', 'deseado': 'ADD_NEW', 'plan': [], 'tramos': [], 'candidatos': tabla,
                'por_que': f'{antes}; ninguna cama de tu biblioteca pasa el Quality Gate: mejor sin música'}
    k = int(hashlib.sha1(str(ctx.get('video') or '').encode('utf-8')).hexdigest()[:8], 16) % len(buenos)
    pts, elegido, partes = buenos[k]
    src = _leer(elegido['ruta'], max_s=600)
    if src is None or src.shape[1] < SR * 5:
        return {'estado': 'NO_MUSIC_REQUIRED', 'deseado': 'ADD_NEW', 'plan': [], 'tramos': [], 'candidatos': tabla, 'por_que': 'la cama no se pudo leer'}
    titulo = Path(elegido['ruta']).stem
    fuente = _bucleable(src) if src.shape[1] < dur * SR else src
    c = (controles or {}).get('musica')
    c_nivel = c if c in ENERGIA else None
    objetivo = float(nivel_voz_db) + MUSICA_BAJO_VOZ_DB[c_nivel] - 2.0
    eq = (('equalizer', 'f=2500:t=q:w=1.2:g=-5'), ('equalizer', 'f=350:t=q:w=1:g=-2'))
    ganancia = objetivo - _rms_tras_eq(src, eq)
    n = int(round(dur * SR))
    duck = _ducking(n, _tramos_voz(ctx.get('palabras')), -6.0)
    huella = F._clave(elegido['ruta'])
    destino = Path(carpeta) / 'musica' / f"AI_MUSIC_autor_{_clave(huella, n, round(objetivo, 1), c_nivel)}.wav"
    if not destino.is_file():
        _escribir_capa(destino, fuente, n, ganancia, duck, fundido_in=2.5, fundido_out=3.5, eq=eq)
    ev = {'tipo': 'musica', 'pista': 'AI MUSIC', 'ini': 0.0, 'dur': round(dur, 3), 'archivo': str(destino), 'asset': f"AI MUSIC · {titulo}",
          'ai': {'id': 'musica', 'tipo': 'musica', 'origen': 'musica', 'fuente': 'tu biblioteca (Film Score: cama tonal)', 'clave': 'musica'}}
    return {'estado': 'ADD_NEW', 'plan': [ev], 'tramos': [(0.0, dur)], 'candidatos': tabla,
            'elegido': {'title': titulo, 'asset_id': 'autor', 'music_fit': pts, 'partes': partes, 'ruta': elegido['ruta']},
            'por_que': f"cama de score «{titulo}» (modo {modo}, music fit {pts:.2f}) de tu biblioteca entre {len(ranking)} candidatas ({antes}); "
                       f"energía por {de_donde}; bajo la voz con ducking por frases"}


def _ambiente_del_autor(contexto, usados):
    """(audio, título, huella) de la mejor grabación del autor para ese entorno que pasa el Quality Gate y aún no se usó, o None."""
    import director_sonido_biblioteca as B
    import director_sonido_fuentes as F
    try:
        rutas = [r for r in B.ambientes(contexto) if r not in usados]
    except Exception:
        return None
    mejores = []
    for r in rutas[:10]:
        q = F.calidad(r, None)
        if q['score'] >= F.UMBRAL and float((q.get('medidas') or {}).get('duracion') or 0) >= 6.0:
            mejores.append((q['score'], r))
    for _q, r in sorted(mejores, key=lambda t: -t[0]):
        src = _leer(r, max_s=120)
        if src is not None and src.shape[1] >= SR * 4:
            usados.add(r)
            return src, Path(r).stem, F._clave(r)
    return None


# ------------------------------------------------------------------------------------------------------------------------------ ambiente
def ambiente(analisis, ctx, controles, carpeta, nivel_voz_db):
    """Las decisiones de ambiente por escena (las del original las aplicó la voz) y lo que se AÑADE de grabaciones autorizadas."""
    import director_sonido_epidemic as EP
    amb = analisis.get('ambiente') or {}
    c = (controles or {}).get('ambiente')
    escenas = [dict(e) for e in amb.get('escenas') or []]
    plan, notas = [], []
    for e in escenas:                                                 # el control manda: «sin» no añade nada; «sutil/inmersivo» lo permite si el
        if c == 'nada' and e.get('decision') in ('ADD_SUBTLE_AMBIENCE', 'REPLACE_AMBIENCE'):     # entorno es claro (nunca en una cama de música)
            e['decision'], e['por_que'] = 'LEAVE_SILENT', 'pediste sin ambiente'
        elif c in ('medio', 'mucho') and e.get('decision') == 'LEAVE_SILENT' and e.get('contexto') in TERMINO_AMBIENTE \
                and float(e.get('confianza') or 0) >= 0.5:
            e['decision'], e['por_que'] = 'ADD_SUBTLE_AMBIENCE', f"pediste ambiente «{c}» y el entorno ({e['contexto'].lower()}) está claro"
    juntas = []
    for e in escenas:
        if e.get('decision') not in ('ADD_SUBTLE_AMBIENCE', 'REPLACE_AMBIENCE'):
            continue
        if juntas and juntas[-1]['contexto'] == e.get('contexto') and abs(float(e['ini']) - juntas[-1]['fin']) < 0.5:
            juntas[-1]['fin'] = float(e['fin'])
        else:
            juntas.append({'contexto': e.get('contexto'), 'ini': float(e['ini']), 'fin': float(e['fin'])})
    epidemic = EP.configurada()
    c_nivel = c if c in ENERGIA else None
    palabras = ctx.get('palabras') or []
    usados, usados_autor, sin = set(), set(), []
    for j in juntas:
        termino = TERMINO_AMBIENTE.get(j['contexto'], 'room tone')
        src, entrada, motivo, fuente_txt = None, None, 'sin proveedor', 'Epidemic Sound (caché profesional)'
        if epidemic:
            r, cands = EP.buscar_sfx(termino, limit=12)
            buenos = [x for x in cands if not x.get('solo_preview') and float(x.get('duracion') or 0) >= 8.0 and x['asset_id'] not in usados]
            buenos.sort(key=lambda x: (-sum(w in str(x.get('title') or '').lower() for w in termino.split()), -float(x.get('duracion') or 0)))
            if r.ok and buenos:
                elegido = buenos[0]
                entrada, motivo = EP.materializar('ambience', elegido, query=termino, uso=str(ctx.get('video') or ''))
                src = _leer(entrada['local_path'], max_s=120) if entrada else None
                if src is not None and src.shape[1] >= SR * 4:
                    usados.add(elegido['asset_id'])
                else:
                    src = None
        if src is None:                                               # v5.37: la grabación del autor de ESE entorno
            local = _ambiente_del_autor(j['contexto'], usados_autor)
            if local is not None:
                src, titulo, huella = local
                entrada = {'asset_id': 'autor', 'title': titulo, 'file_hash': huella}
                fuente_txt = 'tu biblioteca (grabación de ambiente)'
        if src is None:
            sin.append(j)
            notas.append(f"{j['contexto'].lower()}: ninguna grabación autorizada de ese entorno ({motivo}) → silencio")
            continue
        a, b = j['ini'], j['fin']
        n = int(round((b - a) * SR))
        objetivo = float(nivel_voz_db) + AMBIENTE_BAJO_VOZ_DB[c_nivel]
        eq = (('highpass', 'f=120'), ('equalizer', 'f=2200:t=q:w=1.5:g=-6'))
        ganancia = objetivo - _rms_tras_eq(src, eq)
        tramos = [(max(0.0, x - a), y - a) for x, y in _tramos_voz(palabras) if y > a and x < b]
        destino = Path(carpeta) / 'ambiente' / f"AI_AMBIENCE_{entrada['asset_id']}_{_clave(entrada['file_hash'], a, b, round(objetivo, 1))}.wav"
        if not destino.is_file():
            _escribir_capa(destino, _bucleable(src, 1.0), n, ganancia, _ducking(n, tramos, -4.0), fundido_in=0.8, fundido_out=0.8, eq=eq)
        plan.append({'tipo': 'sonido', 'pista': 'AI AMBIENCE', 'ini': round(a, 3), 'dur': round(b - a, 3), 'archivo': str(destino),
                     'asset': f"AI AMBIENCE · {entrada.get('title')}",
                     'ai': {'id': f"ambiente-{len(plan) + 1}", 'tipo': 'ambiente', 'origen': 'ambiente', 'fuente': fuente_txt,
                            'clave': f"ambiente|{j['contexto']}|{round(a, 1)}"}})
        notas.append(f"{j['contexto'].lower()} {a:.1f}–{b:.1f} s: «{entrada.get('title')}» muy bajo, con ducking")
    for e in escenas:                                                 # lo que no encontró grabación de su entorno, en silencio (y dicho)
        if e.get('decision') in ('ADD_SUBTLE_AMBIENCE', 'REPLACE_AMBIENCE') and any(
                j['contexto'] == e.get('contexto') and j['ini'] - 0.01 <= float(e['ini']) < j['fin'] for j in sin):
            e['decision'] = 'LEAVE_SILENT'
            e['por_que'] = 'le iría un ambiente sutil, pero no hay una grabación profesional de ese entorno: mejor silencio'
    return {'escenas': escenas, 'plan': plan, 'resumen': '; '.join(notas) or amb.get('resumen') or ''}
