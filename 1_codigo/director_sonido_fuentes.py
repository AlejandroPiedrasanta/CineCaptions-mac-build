# CineCaptions · By Cinema Productions
# 1_codigo/director_sonido_fuentes.py — «AI Sound Director»: de dónde sale cada sonido (SOUND ASSET STRATEGY) y el QUALITY GATE de cada archivo.
"""
Prioridad para diseños NUEVOS (decisión del usuario, 2026-10-21):
    1 procedural / a la medida (director_sonido_sintesis) · 2 Epidemic autorizado (director_sonido_epidemic) · 3 caché profesional aprobada ·
    4 biblioteca curada (la del autor, la que el usuario apruebe) · 5 LEGACY local (2_recursos/sfx_library) = DISABLED_FOR_NEW_DESIGN, solo si un
    asset pasa el Quality Gate y el usuario lo aprueba · 6 SILENCIO. Un silencio profesional es mejor que un SFX malo.

`calidad(ruta)` → QUALITY SCORE 0–100 con sus motivos (cada penalización explicada): clipping, ruido de fondo, frecuencia de muestreo, equilibrio
espectral (apagado / áspero), graves (DC, rumble por debajo de 30 Hz), transitorio (ataque), duración útil, estéreo (fase), formato con pérdida
(bitrate) y cresta (producción). Con caché por huella del archivo. Por debajo de UMBRAL: REJECT aunque el archivo exista.
`candidatos(tipo)` → archivos de la biblioteca del autor por carpeta (whoosh, golpe, riser, ui, tonal); `elegir(candidatos, objetivo)` → nunca el
primero: puntúa quality, duration_fit, spectral_fit (contra el brillo de la paleta), energy_fit y recent_similarity, y devuelve el mejor + el ranking.
"""
import hashlib
import re
from pathlib import Path

import numpy as np

UMBRAL = 70
LEGACY_LOCAL = 'DISABLED_FOR_NEW_DESIGN'
BIBLIOTECA_AUTOR = Path(r'E:\VFX-EDICION VIDEOS\DAVINCI RESOLVE\EFECTOS SONIDO\UTILES')      # licencias: el autor responde (memoria recursos-del-autor)
CARPETAS = {   # tipo → subcarpetas de la biblioteca del autor (por nombre; se ignora lo que no exista)
    'whoosh': ('Artlist - 200+ Sound Effects/Whooshes', 'Artlist - 200+ Sound Effects/Transitions', 'Whooshes', '1_Sfx - Varios/WHOOSH', 'Cinematic SFX/WHOOSH'),
    'golpe': ('Cinematic SFX/IMPACTOS', '2_Sfx - Cinematic', 'Artlist - 200+ Sound Effects/Impact', 'Artlist - 200+ Sound Effects/Hits', '1_Sfx - Varios/IMPACTOS'),
    'riser': ('Artlist - 200+ Sound Effects/Risers', '2_Sfx - Cinematic', '1_Sfx - Varios/RISERS Y TENSION', 'Cinematic SFX/RISERS Y TENSION', 'SFX RISEX'),
    'ui': ('Artlist - 200+ Sound Effects/Menus', '1_Sfx - Varios/CLICKS Y UI'),
    'tonal': ('Artlist - 200+ Sound Effects/Pulses', 'Artlist - 200+ Sound Effects/Mysterious'),
}
EXT = ('.wav', '.mp3', '.aif', '.aiff', '.flac', '.ogg', '.m4a')
CARPETAS['trazo'] = CARPETAS['ui'] + ('Cinematic SFX/OBJETOS Y FOLEY', '1_Sfx - Varios/OTROS')
# SEMANTIC FIT por el nombre del archivo: lo que encaja con cada diseño, lo que es un OBJETO concreto (suena a eso, no a un gráfico) y lo que nunca va
SEMANTICA = {
    'golpe': ('impact', 'hit', 'slam', 'boom', 'cinematic', 'sub', 'drop', 'braam', 'thud', 'designed', 'trailer', 'bass', 'deep', 'titanic', 'epic'),
    'whoosh': ('whoosh', 'swoosh', 'swish', 'swipe', 'transition', 'air', 'woosh', 'pass', 'swing', 'zip', 'sweep'),
    'riser': ('riser', 'rise', 'swell', 'build', 'uplift', 'tension', 'sweep', 'reverse', 'risex'),
    'ui': ('click', 'tap', 'ui', 'button', 'select', 'pop', 'tick', 'interface', 'menu', 'blip', 'beep', 'notification', 'seleccion', 'taping', 'tapping'),
    'tonal': ('chime', 'bell', 'ping', 'sparkle', 'shimmer', 'notification', 'tone', 'glass', 'twinkle', 'positive', 'magic', 'success', 'chord',
              'note', 'positivo', 'tonal'),
    'trazo': ('marker', 'pen', 'pencil', 'scribble', 'draw', 'write', 'writing', 'chalk', 'brush', 'sketch'),
}
OBJETOS = ('plastic', 'pottery', 'metal', 'metallic', 'steel', 'armor', 'sword', 'wood', 'wooden', 'table', 'rock', 'stone', 'glass', 'debris', 'breaking',
           'door', 'car', 'gun', 'weapon', 'military', 'target', 'punch', 'combat', 'fight', 'bat', 'baseball', 'whack', 'smack', 'wet', 'body',
           'kitchen', 'bottle', 'paper', 'thunder', 'fire', 'steam', 'anime', 'wobbly')
NUCLEO = {   # sin al menos una de estas palabras, el archivo no es de ese tipo (un «Reverse Wind Riser» no es un golpe aunque diga «Cinematics»)
    'golpe': ('impact', 'hit', 'slam', 'boom', 'braam', 'thud', 'drop', 'bass'),
    'whoosh': ('whoosh', 'swoosh', 'swish', 'swipe', 'transition', 'woosh', 'pass'),
    'riser': ('riser', 'rise', 'swell', 'build', 'uplift', 'reverse', 'risex'),
    'ui': ('click', 'tap', 'ui', 'button', 'select', 'pop', 'tick', 'blip', 'beep', 'interface', 'seleccion', 'taping', 'tapping'),
    'tonal': ('chime', 'bell', 'ping', 'sparkle', 'shimmer', 'shimmering', 'tone', 'twinkle', 'notification', 'chord', 'note', 'positivo'),
    'trazo': ('marker', 'pen', 'pencil', 'scribble', 'draw', 'write', 'writing', 'chalk', 'sketch'),
}
OSCURO = ('dark', 'ominous', 'sinister', 'evil', 'mysterious', 'creepy', 'suspense', 'horror')     # no van con un video luminoso (brillo ≥ 0,5)
NUNCA = ('fart', 'burp', 'meme', 'cartoon', 'scream', 'laugh', 'baby', 'vomit', 'toilet', 'moan', 'vocal', 'voice', 'song', 'guitar', 'piano',
         'arpeggio', 'creepy', 'horror', 'ghost', 'scary', 'zombie', 'monster', 'funny', 'comedy', 'cry')
_CACHE = {}
_DISCO = {'cargado': False, 'cambios': 0}                 # v5.34: las medidas también en disco (sound_director/cache/quality_gate.json)


def _ruta_cache():
    import director_sonido_estado as E
    return E.CARPETA / 'cache' / 'quality_gate.json'


def _cargar_disco():
    if _DISCO['cargado']:
        return
    _DISCO['cargado'] = True
    try:
        import archivos_seguros
        datos = archivos_seguros.leer_json(_ruta_cache(), {}) or {}
        for k, v in (datos.get('entradas') or {}).items():
            clave, _, tipo = str(k).partition('|')
            _CACHE.setdefault((clave, tipo or None), v)
    except Exception:
        pass


def guardar_cache():
    """Las medidas nuevas del Quality Gate, a disco (el mismo archivo con la misma huella no se vuelve a medir en el próximo GO)."""
    if not _DISCO['cambios']:
        return
    try:
        import archivos_seguros
        archivos_seguros.escribir_json(_ruta_cache(), {'version': 1, 'entradas': {f'{k[0]}|{k[1] or ""}': v for k, v in _CACHE.items()}},
                                       default=lambda o: float(o) if hasattr(o, '__float__') else str(o))
        _DISCO['cambios'] = 0
    except Exception:
        pass


def _leer(ruta, max_s=12.0):
    """(muestras (canales, n) a 48 kHz, tasa nativa, bitrate, duración) o None."""
    import av
    try:
        with av.open(str(ruta)) as c:
            a = c.streams.audio[0]
            tasa, br = int(a.codec_context.sample_rate or 0), int(a.codec_context.bit_rate or c.bit_rate or 0)
            dur = float(c.duration / 1e6) if c.duration else 0.0
            rs = av.AudioResampler(format='fltp', layout='stereo', rate=48000)
            trozos, total = [], 0
            for fr in c.decode(a):
                for g in rs.resample(fr):
                    x = g.to_ndarray()
                    trozos.append(x)
                    total += x.shape[1]
                if total > max_s * 48000:
                    break
            if not trozos:
                return None
            x = np.concatenate(trozos, axis=1).astype(np.float32)
            return x, tasa, br, dur or x.shape[1] / 48000.0
    except Exception:
        return None


def _clave(ruta):
    p = Path(ruta)
    st = p.stat()
    return hashlib.sha1(f'{p.resolve()}|{st.st_size}|{int(st.st_mtime)}'.encode('utf-8')).hexdigest()[:16]


def calidad(ruta, tipo=None):
    """QUALITY SCORE 0–100 y por qué (cada punto que se resta, con su medida)."""
    _cargar_disco()
    try:
        k = (_clave(ruta), tipo)
    except OSError:
        return {'score': 0, 'motivos': ['no existe'], 'medidas': {}}
    if k in _CACHE:
        return _CACHE[k]
    d = _leer(ruta)
    if d is None:
        r = {'score': 0, 'motivos': ['no se puede decodificar'], 'medidas': {}}
        _CACHE[k] = r
        return r
    x, tasa, br, dur = d
    m = x.mean(axis=0)
    pico = float(np.abs(x).max()) or 1e-9
    puntos, motivos, med = 100, [], {}

    def menos(n, motivo):
        nonlocal puntos
        puntos -= n
        motivos.append(f'−{n} {motivo}')
    pegadas = float(np.mean(np.abs(x) >= 0.999))
    med['clipping_pct'] = round(100 * pegadas, 4)
    if pegadas > 0.0001:
        menos(25, f'clipping ({100 * pegadas:.3f} %)')
    med['tasa'], med['bitrate'], med['duracion'] = tasa, br, round(dur, 3)
    if tasa and tasa < 44100:
        menos(15, f'muestreo bajo ({tasa} Hz)')
    if str(ruta).lower().endswith('.mp3') and br and br < 160000:
        menos(10, f'mp3 de {br // 1000} kbps')
    env = np.sqrt(np.convolve(m.astype(np.float64) ** 2, np.ones(480) / 480, 'same') + 1e-12)
    env_db = 20 * np.log10(env / pico + 1e-12)
    ruido = float(np.percentile(env_db, 8)) if env_db.size else -120
    med['fondo_rel_pico_db'] = round(ruido, 1)
    if ruido > -45 and tipo in ('golpe', 'ui', 'whoosh'):
        menos(15, f'ruido de fondo alto ({ruido:.0f} dB bajo el pico)')
    dc = float(abs(m.mean()))
    if dc > 0.01:
        menos(10, f'DC {dc:.3f}')
    n = min(m.size, 48000 * 4)
    P = np.abs(np.fft.rfft(m[:n] * np.hanning(n))) ** 2 if n > 1024 else None
    if P is not None:
        f = np.fft.rfftfreq(n, 1 / 48000)
        tot = P.sum() + 1e-12
        cent = float((P * f).sum() / tot)
        sub = float(P[f < 30].sum() / tot)
        aspero = float(P[(f > 2500) & (f < 5000)].sum() / tot)
        med.update(centroide_hz=round(cent), sub30=round(sub, 3), aspereza=round(aspero, 3))
        if sub > 0.3:
            menos(10, f'rumble por debajo de 30 Hz ({100 * sub:.0f} %)')
        if cent < 250 and tipo not in ('golpe',):
            menos(10, f'apagado (centroide {cent:.0f} Hz)')
        if aspero > 0.45:
            menos(10, f'áspero ({100 * aspero:.0f} % en 2,5–5 kHz)')
    i_pico = int(np.argmax(env))
    a10 = int(np.argmax(env[:i_pico + 1] >= 0.1 * env[i_pico])) if i_pico > 0 else 0
    ataque_ms = (i_pico - a10) / 48.0
    med['ataque_ms'] = round(ataque_ms, 1)
    if tipo in ('golpe', 'ui') and ataque_ms > 25:
        menos(10, f'transitorio blando ({ataque_ms:.0f} ms) para un {tipo}')
    rms = float(np.sqrt(np.mean(m.astype(np.float64) ** 2)) + 1e-12)
    cresta = 20 * np.log10(pico / rms)
    med['cresta_db'] = round(cresta, 1)
    if tipo == 'golpe' and cresta < 8:
        menos(10, f'golpe aplastado (cresta {cresta:.0f} dB)')
    if x.shape[0] == 2:
        l, r = x[0].astype(np.float64), x[1].astype(np.float64)
        corr = float(np.dot(l, r) / (np.sqrt(np.dot(l, l) * np.dot(r, r)) + 1e-12))
        med['correlacion_lr'] = round(corr, 3)
        if corr < 0:
            menos(15, f'fase invertida entre canales ({corr:.2f}: desaparece en mono)')
    util = float(np.sum(env_db > -40)) / 48000.0
    med['duracion_util_s'] = round(util, 3)
    if util < 0.04 or dur > 20:
        menos(10, f'duración útil rara ({util:.2f} s de {dur:.1f} s)')
    r = {'score': int(max(0, puntos)), 'motivos': motivos or ['sin defectos medidos'], 'medidas': med}
    _CACHE[k] = r
    _DISCO['cambios'] += 1
    return r


def _palabras(ruta):
    """Las palabras del nombre y de su carpeta (v5.37: el autor ordena por carpetas: «Whooshes/…», «SELECCION (3)», «Chord Hits/…»)."""
    p = Path(ruta)
    return re.findall(r'[a-z0-9áéíóúñ]+', f'{p.stem} {p.parent.name}'.lower())


def _tiene(palabras, termino):
    """La palabra ENTERA (o su plural; los términos largos, también como prefijo: whoosh → whooshes): «pen» no está en «pensamiento»."""
    if ' ' in termino:
        return termino in ' '.join(palabras)
    return any(w == termino or w in (termino + 's', termino + 'es') or (len(termino) >= 5 and w.startswith(termino)) for w in palabras)


def semantica(ruta, tipo, brillo=None):
    """SEMANTIC FIT 0–1 por el nombre: +0,3 por cada palabra del diseño, −0,5 por cada objeto concreto (suena a ese objeto, no a un gráfico),
    −0,4 por un tono oscuro en un video luminoso; 0 si es algo que nunca va."""
    w = _palabras(ruta)
    if any(_tiene(w, p) for p in NUNCA):
        return 0.0
    bien = sum(1 for p in SEMANTICA.get(tipo, ()) if _tiene(w, p))
    mal = sum(1 for p in OBJETOS if _tiene(w, p))
    oscuro = sum(1 for p in OSCURO if _tiene(w, p)) if (brillo is not None and brillo >= 0.5) else 0
    valor = float(np.clip(0.4 + 0.3 * bien - 0.5 * mal - 0.4 * oscuro, 0.0, 1.0))
    if tipo in NUCLEO and not any(_tiene(w, p) for p in NUCLEO[tipo]):
        valor = min(valor, 0.4)                                      # sin palabra núcleo: no se elige
    return valor


def familia(ruta):
    """La «familia» de un archivo (su pack o su serie: «SoundBits - Hitting»): dos de la misma familia seguidos suenan repetidos."""
    partes = [p.strip() for p in Path(ruta).stem.split(' - ')]
    if len(partes) > 2:
        return ' - '.join(partes[:2]).lower()
    return re.sub(r'[\s_]*\d+$', '', Path(ruta).stem.lower())           # «Copy of Hit Slam Metal 04» → «copy of hit slam metal»


def candidatos(tipo, base=None, por_carpeta=30, extra=60):
    """Archivos de la biblioteca del autor para ese tipo, repartidos entre sus carpetas (no solo las primeras por orden alfabético) y, v5.37, los
    de TODO su material indexado (director_sonido_biblioteca: Film Score, ambientes, clics…) que encajan por su nombre. Sin `base` explícita."""
    salida = []
    for sub in CARPETAS.get(tipo, ()):
        d = (Path(base) if base else BIBLIOTECA_AUTOR) / sub
        if d.is_dir():
            todos = sorted(p for p in d.rglob('*') if p.suffix.lower() in EXT and p.is_file())
            paso = max(1, len(todos) // por_carpeta)
            salida += todos[::paso][:por_carpeta]
    if base is None and extra:
        try:
            import director_sonido_biblioteca as B
            ya = {str(p) for p in salida}
            salida += [Path(r) for r in B.de_categoria(tipo, extra) if r not in ya]
        except Exception:
            pass
    return salida


def elegir(lista, objetivo, usados=None):
    """El mejor candidato para `objetivo` {'tipo', 'dur', 'brillo' 0–1, 'energia' 0–1}: quality ≥ UMBRAL y luego duration_fit, spectral_fit,
    energy_fit y recent_similarity. Devuelve (ruta | None, ranking [(puntos, ruta, desglose)])."""
    usados = usados or {}
    familias = {}
    for r, n in usados.items():
        familias[familia(r)] = familias.get(familia(r), 0) + n
    ranking = []
    for ruta in lista:
        sem = semantica(ruta, objetivo.get('semantica') or objetivo.get('tipo'), objetivo.get('brillo'))
        if sem < 0.5:
            ranking.append((-1, str(ruta), {'semantic_fit': round(sem, 2), 'rechazado': ['no encaja con el diseño (por su nombre)']}))
            continue
        q = calidad(ruta, objetivo.get('tipo'))
        if q['score'] < UMBRAL:
            ranking.append((-1, str(ruta), {'quality': q['score'], 'rechazado': q['motivos']}))
            continue
        med = q['medidas']
        dur_u = med.get('duracion_util_s') or med.get('duracion') or 0.0
        tipo = objetivo.get('tipo')
        if tipo in ('golpe', 'tonal'):                               # la cola se recorta con fundido: basta con que tenga ataque y cuerpo
            dfit = 1.0 if 0.2 <= dur_u <= 4.0 else (0.6 if dur_u > 4.0 else dur_u / 0.2)
        elif tipo == 'riser':                                         # se usa el final: vale si dura al menos lo que hace falta
            dfit = float(min(1.0, dur_u / max(0.1, objetivo.get('dur', 1.0))))
        else:
            dfit = float(np.exp(-abs(np.log(max(dur_u, 0.02) / max(objetivo.get('dur', 0.5), 0.02)))))
        cent = med.get('centroide_hz') or 1500
        brillo = float(np.clip(np.log2(max(cent, 100) / 400.0) / 4.0, 0, 1))
        brillo_obj = 0.3 if tipo == 'golpe' else objetivo.get('brillo', 0.5)     # un golpe con cuerpo es oscuro por naturaleza
        sfit = 1.0 - abs(brillo - brillo_obj)
        efit = 1.0 - abs(float(np.clip((med.get('cresta_db', 12) - 6) / 14, 0, 1)) - objetivo.get('energia', 0.5))
        rep = 0.5 * usados.get(str(ruta), 0) + 0.15 * familias.get(familia(ruta), 0)
        puntos = 0.25 * sem + 0.25 * q['score'] / 100 + 0.25 * dfit + 0.15 * sfit + 0.1 * efit - rep
        ranking.append((round(puntos, 3), str(ruta), {'semantic_fit': round(sem, 2), 'quality': q['score'], 'duration_fit': round(dfit, 2),
                                                      'spectral_fit': round(sfit, 2), 'energy_fit': round(efit, 2), 'recent_similarity': round(rep, 2)}))
    ranking.sort(key=lambda r: -r[0])
    mejor = next((r[1] for r in ranking if r[0] >= 0), None)
    return mejor, ranking


def leer_para_mezcla(ruta, dur=None, fundido_s=0.03):
    """El archivo elegido como (2, n) a 48 kHz, recortado a `dur` (si se da) con su fundido de salida: siempre una COPIA en memoria."""
    d = _leer(ruta, max_s=(dur or 10.0) + 0.5)
    if d is None:
        return None
    x = d[0]
    if dur:
        x = x[:, :int(dur * 48000)]
    k = min(x.shape[1], int(fundido_s * 48000))
    if k:
        x = x.copy()
        x[:, -k:] *= np.linspace(1, 0, k)
    return x
