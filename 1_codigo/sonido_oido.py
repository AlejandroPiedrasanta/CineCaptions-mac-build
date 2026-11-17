# CineCaptions · By Cinema Productions
# 1_codigo/sonido_oido.py — el «Oído» del sonido (v5.93): lo que earshot (github.com/Leonxlnx/earshot, MIT) midió en películas de lanzamiento
# profesionales, aplicado a la biblioteca del autor en TODOS los estilos (todos pasan por sonido_skill). Solo sus medidas y criterios: NUNCA sus
# sonidos hechos por código (el usuario, 2026-10-27: «NO USES SONIDOS CREADOS POR IA»).
"""
    Cama.de_video(video, ctx, carpeta)  sonoridad K (BS.1770) del audio del video en bloques de 50 ms, en tiempo del TIMELINE (con Quitar pausas)
    Cama.ajuste(t)                      dB que se mueve un SFX para seguir a la voz medida en el segundo anterior (≈0 donde se afinaron los niveles)
    OFFSET_MS                           dónde cae cada tipo respecto a su cuadro (preset «launch»: whoosh +37 ms tras el corte, riser −23 ms…)
    en_rafaga / cerrar_rafagas          ráfagas de UI con su separación mínima (pops 114 ms, clics 85 ms…) y el acento al final
    auditar(x, pool) / fallos_de        las pruebas de «sfx check» sobre cada archivo (en caché por tamaño y fecha)
    filtrar_pools(pools, lib, cat)      fuera de GO los archivos con fallos GRAVES (si su pool conserva alguno)
    caidas_musica(filas)                la música baja 8 dB 0,4 s antes de un golpe fuerte y vuelve en el golpe («stop-down»)
    escuchar(video)                     la mezcla completa medida → LUFS, pico, LRA, semáforo de cada sonido, veredicto y acciones (la página)
    arreglar(video)                     aplica las acciones con arreglo automático (nivel, cuadro) y vuelve a hornear

Medidas de earshot que se usan (docs/SFX.md y skills/earshot/SKILL.md, versión 0.4): offsets medianos de cada rol frente al corte más cercano;
min_gap_ms de las ráfagas; «stop-down» (el 53 % de los golpes fuertes llega tras una caída de la música de ≥ 6 dB en los 0,5 s previos, frente al 9 %
al azar: bajar 6–12 dB 0,3–0,5 s); sincronía verde ≤ 1 cuadro, ámbar ≤ 100 ms; máster ≤ −1 dBTP; cabeza/cola limpias a −30 dB; DC > −40 dB re pico;
cola cortada aún sobre −45 dB; cola que sube > 6 dB; doble ataque (envolvente 25 ms, picos a < 6 dB del máximo con valle ≥ 10 dB en 0,5 s).
"""
import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np

SR = 48000
BLOQUE = 0.05                      # earshot: la «cama» es la mediana de bloques de 50 ms (K) en el segundo previo al sonido
SILENCIO_LUFS = -70.0
VOZ_REF = -14.0                    # sonoridad de la voz (mediana de bloques de 50 ms mientras se habla) de PRUEBAS-EN-ESPAÑOL (1).mov, el video
                                   # donde se afinaron NIVEL y PULIDO (2026-10-27; medido −14,1): ahí los SFX quedan como el usuario los aprobó
PAUSA_DB = -2.0                    # en una pausa (sin voz que lo tape) el sonido va un poco más bajo
AJUSTE_LOCAL = (-6.0, 6.0)         # cuánto sigue a la frase (más fuerte / más suave que la voz media del video)
AJUSTE_TOTAL = (-10.0, 8.0)
CAMA_VERSION = 1

# --------------------------------------------------------------------------------------------- sincronía por tipo (preset «launch» de earshot)
# ms entre el cuadro del evento y el punto de sync del sonido (+ = el sonido después). Lo que APARECE ya alinea su primer sonido audible con el
# primer cuadro de la animación (regla del usuario, 2026-10-27): solo se le suma el matiz medido (clic −11, campana −20, pop +4). Lo que SUBE hacia
# el momento lleva su pico/fin: whoosh corto +37 ms tras el corte, whoosh largo +3, riser termina 23 ms antes del golpe, flash (obturador) +9.
OFFSET_MS = {'swoosh': 37, 'whoosh': 3, 'riser': -23, 'impacto': 0, 'flash': 9, 'mouse': -11, 'boton_on': -11, 'boton_off': -11,
             'ding': -20, 'notif': -20, 'pop': 4, 'burbuja': 4}

# --------------------------------------------------------------------------------------------- ráfagas (min_gap_ms de earshot)
RAFAGA_MS = {'pop': 114, 'burbuja': 114, 'mouse': 85, 'boton_on': 85, 'boton_off': 85, 'ding': 110}
RAFAGAS_EN = ('cinetica', 'lista')         # estilos con muchos textos seguidos; elegante y dinámico siguen con su separación de siempre
RAFAGA_MAX = 6                             # más largo ya no es una ráfaga sino un tecleo
RAFAGA_FANTASMA_DB = -3.0                  # las notas de paso, más suaves…
RAFAGA_ACENTO_DB = 1.0                     # …y el acento al final (earshot: mix.runs.accent_at_end)

# --------------------------------------------------------------------------------------------- la música respira (stop-down)
CAIDA_POOLS = ('impacto', 'riser', 'whoosh', 'acento')
CAIDA_DB, CAIDA_S, CAIDA_BAJA_S, CAIDA_SUBE_S, CAIDA_SEPARACION = 8.0, 0.4, 0.08, 0.05, 2.0

# --------------------------------------------------------------------------------------------- auditoría («sfx check»)
GRAVES = ('silencio', 'saturado', 'doble')                 # fuera de GO si su pool conserva otro
ARREGLABLES = ('dc', 'borde', 'cortado')                   # se arreglan al hornear (DC fuera, fundidos)
AVISOS = ('clic', 'resonancia', 'cola_sube')               # solo se cuentan
TONALES = ('ding', 'notif', 'dinero', 'positivo', 'error', 'boton_on', 'boton_off', 'acento', 'shine', 'kinetic')
GOLPES = ('impacto',)
AUDIT_VERSION = 1
NOMBRE_FALLO = {'silencio': 'casi mudo', 'saturado': 'saturado', 'doble': 'golpe doble', 'dc': 'desplazado (DC)', 'borde': 'empieza o acaba con clic',
                'cortado': 'cola cortada', 'clic': 'clic suelto', 'resonancia': 'resonancia metálica', 'cola_sube': 'la cola vuelve a subir'}

# --------------------------------------------------------------------------------------------- veredicto
VERDE_MS = 100.0                   # ámbar hasta aquí (verde = 1 cuadro)
TP_TECHO = -1.0
LUFS_WEB = (-16.0, -12.0)
PISA_VOZ_DB = -1.5                 # un SFX a menos de 1,5 dB de la voz de su frase (K, donde suena) la tapa. Medido: lo aprobado queda debajo
                                   # (dinámico ≤ −6,2 dB; los pops del pulido en cinética ≤ −2,5 dB en PRUEBAS-EN-ESPAÑOL (1).mov)
TAPADO_DB = -10.0                  # un SFX más de 10 dB bajo la música en su instante no se oye
TEXTURAS = ('kinetic',)            # van debajo a propósito (el usuario, 2026-10-27: «los aros… bájales el sonido»): nunca «tapado»
VEREDICTOS = ('Listo para publicar', 'Casi', 'Revisar')


def log(msg, nivel='info'):
    try:
        import sonido_skill
        sonido_skill.log('Oído: ' + str(msg), nivel)
    except Exception:
        pass


# ============================================================================================ sonoridad K (ITU-R BS.1770)
def _biquad(b, a, f, sr):
    z1 = np.exp(-2j * np.pi * f / sr)
    z2 = z1 * z1
    return (b[0] + b[1] * z1 + b[2] * z2) / (a[0] + a[1] * z1 + a[2] * z2)


_K = {}


def respuesta_k(n, sr=SR):
    """|H| del filtro K (estante +4 dB en 1,7 kHz + paso alto RLB de 38 Hz) en los bins de un rfft de n muestras."""
    clave = (n, sr)
    if clave not in _K:
        f = np.fft.rfftfreq(n, 1.0 / sr)
        g, q, fc = 3.999843853973347, 0.7071752369554196, 1681.974450955533
        A, w0 = 10 ** (g / 40), 2 * np.pi * fc / sr
        al, c, sa = math.sin(w0) / (2 * q), math.cos(w0), math.sqrt(10 ** (g / 40))
        h = _biquad((A * ((A + 1) + (A - 1) * c + 2 * sa * al), -2 * A * ((A - 1) + (A + 1) * c), A * ((A + 1) + (A - 1) * c - 2 * sa * al)),
                    ((A + 1) - (A - 1) * c + 2 * sa * al, 2 * ((A - 1) - (A + 1) * c), (A + 1) - (A - 1) * c - 2 * sa * al), f, sr)
        q, fc = 0.5003270373238773, 38.13547087602444
        w0 = 2 * np.pi * fc / sr
        al, c = math.sin(w0) / (2 * q), math.cos(w0)
        h = h * _biquad(((1 + c) / 2, -(1 + c), (1 + c) / 2), (1 + al, -2 * c, 1 - al), f, sr)
        _K[clave] = np.abs(h).astype(np.float32)
    return _K[clave]


def filtrar_k(x, sr=SR):
    """x (canales, n) con el peso K (en frecuencia: rápido y de sobra para medir sonoridad)."""
    n = x.shape[1]
    if n < 16:
        return x
    return np.fft.irfft(np.fft.rfft(x, axis=1) * respuesta_k(n, sr), n=n, axis=1).astype(np.float32)


def lufs_bloques(x, sr=SR, bloque=BLOQUE):
    """Sonoridad (LUFS, sin puerta) de cada bloque completo de `bloque` s de x (canales, n)."""
    m = int(round(bloque * sr))
    k = x.shape[1] // m
    if not k:
        return np.zeros(0, np.float32)
    y = filtrar_k(x, sr)[:, :k * m].reshape(x.shape[0], k, m)
    p = (y.astype(np.float64) ** 2).mean(axis=2).sum(axis=0)
    return np.maximum(-0.691 + 10 * np.log10(np.maximum(p, 1e-12)), SILENCIO_LUFS).astype(np.float32)


def lufs(x, sr=SR):
    """Sonoridad de todo x (sin puerta): para comparar un SFX con lo que suena a la vez."""
    if x.shape[1] < 16:
        return SILENCIO_LUFS
    y = filtrar_k(x, sr).astype(np.float64)
    return max(SILENCIO_LUFS, float(-0.691 + 10 * np.log10(max((y ** 2).mean(axis=1).sum(), 1e-12))))


# ============================================================================================ la cama (la voz del video)
class Cama:
    """La sonoridad del audio del video cada 50 ms en tiempo del timeline y la de la voz mientras habla."""

    def __init__(self, bloques, palabras=None):
        self.l = np.asarray(bloques, np.float32)
        self.voz = None
        if self.l.size and palabras:
            m = np.zeros(self.l.size, bool)
            for p in palabras:
                a, b = int(float(p.get('start') or 0) / BLOQUE), int(math.ceil(float(p.get('end') or 0) / BLOQUE))
                m[max(0, a):max(0, min(self.l.size, b))] = True
            v = self.l[m & (self.l > -60)]
            if v.size >= 10:
                self.voz = float(np.median(v))

    @classmethod
    def de_video(cls, video, ctx, carpeta):
        """La de este video (en caché en su carpeta). None si no se puede leer su audio."""
        ctx = ctx or {}
        segs = [tuple(round(float(v), 3) for v in s) for s in ((ctx.get('recorte') or {}).get('segmentos') or [])] or None
        try:
            p = Path(str(video))
            firma = hashlib.sha1(f'{p.resolve()}|{p.stat().st_size}|{int(p.stat().st_mtime)}|{segs}|{CAMA_VERSION}'.encode()).hexdigest()[:16]
        except OSError:
            return None
        ruta = Path(carpeta) / 'oido_cama.npz'
        try:
            d = np.load(ruta, allow_pickle=False)
            if str(d['firma']) == firma:
                return cls(d['l'], ctx.get('palabras'))
        except Exception:
            pass
        try:
            import director_sonido_medir as M
            partes, resto = [], np.zeros((2, 0), np.float32)
            m = int(round(BLOQUE * SR))
            for x in M.trozos(str(video), segmentos=segs, canales=2):
                x = np.asarray(x, np.float32)
                if x.shape[0] == 1:
                    x = np.vstack((x, x))
                resto = np.concatenate((resto, x[:2]), axis=1)
                k = (resto.shape[1] // m) * m
                if k:
                    partes.append(lufs_bloques(resto[:, :k]))
                    resto = resto[:, k:]
            if resto.shape[1]:
                partes.append(lufs_bloques(np.pad(resto, ((0, 0), (0, m - resto.shape[1])))))
            l = np.concatenate(partes) if partes else np.zeros(0, np.float32)
        except Exception:
            log('no pude medir la voz del video: los sonidos van con su nivel fijo', 'aviso')
            return None
        try:
            Path(carpeta).mkdir(parents=True, exist_ok=True)
            tmp = Path(carpeta) / 'oido_cama.tmp.npz'
            np.savez(tmp, l=l, firma=np.array(firma))
            tmp.replace(ruta)
        except Exception:
            pass
        return cls(l, ctx.get('palabras'))

    def frase(self, t, medio=0.5):
        """Sonoridad de la voz alrededor de t (± medio s, solo bloques con voz). None si ahí no se habla."""
        if self.voz is None:
            return None
        w = self.l[max(0, int((t - medio) / BLOQUE)):max(0, int((t + medio) / BLOQUE))]
        w = w[w > self.voz - 15.0]
        return float(np.median(w)) if w.size >= 4 else None

    def local(self, t):
        """Mediana de la sonoridad en el segundo antes de t (None sin datos)."""
        i1 = int(t / BLOQUE)
        i0 = max(0, i1 - int(round(1.0 / BLOQUE)))
        w = self.l[i0:max(i0 + 1, i1)]
        return float(np.median(w)) if w.size else None

    def ajuste(self, t):
        """dB para el SFX que cae en t: la voz del video frente a VOZ_REF + la frase frente a la voz media (pausa: PAUSA_DB). 0 sin voz medida."""
        if self.voz is None:
            return 0.0
        base = self.voz - VOZ_REF
        loc = self.local(t)
        local = PAUSA_DB if loc is None or loc < self.voz - 15.0 else float(np.clip(loc - self.voz, *AJUSTE_LOCAL))
        return round(float(np.clip(base + local, *AJUSTE_TOTAL)), 2)


# ============================================================================================ ráfagas
def en_rafaga(p, e, estilo):
    """¿e sigue la ráfaga de p (mismo pool de UI, separación mínima medida, estilo con ráfagas)? Marca a e con su largo."""
    ms = RAFAGA_MS.get(e.get('pool'))
    if estilo not in RAFAGAS_EN or not ms or p.get('pool') != e.get('pool'):
        return False
    n = int(p.get('n_rafaga') or 1)
    if n >= RAFAGA_MAX or (float(e['segundo']) - float(p['segundo'])) * 1000.0 < ms:
        return False
    e['n_rafaga'] = n + 1
    return True


def cerrar_rafagas(out, gap_pop=0.6):
    """Tras el tope por ventana: una nota de paso sin quien la siga deja de serlo."""
    for a, b in zip(out, out[1:] + [None]):
        if a.get('rafaga') and not (b and b.get('pool') == a.get('pool') and float(b['segundo']) - float(a['segundo']) < gap_pop):
            a['rafaga'] = False
    return out


def ganancia_rafaga(filas, i):
    """dB por su papel en una ráfaga: nota de paso (más suave) o acento final."""
    f = filas[i]
    if f.get('rafaga'):
        return RAFAGA_FANTASMA_DB
    if i and filas[i - 1].get('rafaga') and filas[i - 1].get('pool') == f.get('pool'):
        return RAFAGA_ACENTO_DB
    return 0.0


# ============================================================================================ la música respira
def caidas_musica(filas):
    """Segundos de los golpes fuertes ante los que la música baja (separados ≥ CAIDA_SEPARACION)."""
    out = []
    for f in sorted(filas or [], key=lambda f: float(f['segundo'])):
        if f.get('pool') in CAIDA_POOLS and (not out or float(f['segundo']) - out[-1] >= CAIDA_SEPARACION):
            out.append(round(float(f['segundo']), 3))
    return out


def curva_caidas(n, caidas, sr=SR):
    """Ganancia (n,) de la música: baja CAIDA_DB en [t − CAIDA_S, t] (rampa de CAIDA_BAJA_S) y vuelve en t (CAIDA_SUBE_S)."""
    g = np.ones(n, np.float32)
    piso = 10 ** (-CAIDA_DB / 20)
    for t in caidas or []:
        a, b = int((t - CAIDA_S - CAIDA_BAJA_S) * sr), int((t - CAIDA_S) * sr)
        c, d = int(t * sr), int((t + CAIDA_SUBE_S) * sr)
        if d <= 0 or a >= n:
            continue
        t_ = np.arange(max(0, a), min(n, d))
        v = np.interp(t_, [a, b, c, d], [1.0, piso, piso, 1.0]).astype(np.float32)
        g[t_] = np.minimum(g[t_], v)
    return g


# ============================================================================================ auditoría de la biblioteca
def _env(m, sr, ms):
    k = max(1, int(sr * ms / 1000))
    n = (m.size // k) * k
    return np.sqrt((m[:n].reshape(-1, k) ** 2).mean(axis=1)) if n else np.zeros(0)


def auditar(x, pool=None, sr=SR):
    """Lista de fallos de un sonido (canales, n) — las pruebas de «sfx check» de earshot que sirven para grabaciones reales."""
    fallos = []
    if not x.size or x.shape[1] < 32:
        return ['silencio']
    a = np.abs(x)
    m = a.max(axis=0)
    pk = float(m.max())
    if pk < 10 ** (-60 / 20) or int((m >= pk * 0.01).sum()) < sr * 0.005:
        return ['silencio']
    # saturación: tramos de ≥ 3 muestras pegadas al máximo, o mesetas (≥ 4 muestras iguales) en el pico de un archivo ya normalizado
    pegadas = (a >= 0.999).any(axis=0)
    d = np.diff(np.concatenate(([0], pegadas.astype(np.int8), [0])))
    tramos = int(((np.flatnonzero(d == -1) - np.flatnonzero(d == 1)) >= 3).sum())
    if tramos < 3:
        for c in x:
            cerca = np.abs(c) >= pk * 0.98
            iguales = np.concatenate(([False], np.abs(np.diff(c)) < 1e-7)) & cerca
            dd = np.diff(np.concatenate(([0], iguales.astype(np.int8), [0])))
            tramos += int(((np.flatnonzero(dd == -1) - np.flatnonzero(dd == 1)) >= 3).sum())
    if tramos >= 3:
        fallos.append('saturado')
    # DC: desplazamiento sobre −40 dB del pico
    if float(np.abs(x.mean(axis=1)).max()) > pk * 10 ** (-40 / 20):
        fallos.append('dc')
    # bordes: cabeza (5 ms) o cola (10 ms) por encima de −30 dB del pico en su primera / última muestra
    if m[0] > pk * 0.0316 or m[-1] > pk * 0.0316:
        fallos.append('borde')
    env = _env(m, sr, 10)
    if env.size > 3:
        # cola cortada: el final aún decae por encima de −45 dB
        if env[-1] > pk * 10 ** (-45 / 20) and env.size > 10 and env[-1] < env[-6:-1].max():
            fallos.append('cortado')
        # la cola vuelve a subir > 6 dB: ya en la cola (10 dB bajo el máximo), sostenido 30 ms y audible (sobre −24 dB del máximo)
        e30 = _env(m, sr, 30)
        i = int(np.argmax(e30)) if e30.size else 0
        cola = e30[i:]
        caida = np.flatnonzero(cola < cola[0] * 0.316) if cola.size else np.zeros(0, int)
        if caida.size and cola.size - caida[0] > 3:
            resto = cola[caida[0]:]
            minimo = np.minimum.accumulate(resto)
            sube = (resto > minimo * 2.0) & (resto > float(e30.max()) * 0.063)
            if bool((sube[1:] & sube[:-1]).any()):
                fallos.append('cola_sube')
    # doble ataque en un golpe: envolvente 25 ms, dos picos a < 6 dB del máximo con un valle ≥ 10 dB entre ellos en los primeros 0,5 s
    if pool in GOLPES:
        e25 = _env(m[:int(0.5 * sr)], sr, 25)
        if e25.size >= 3:
            top = float(e25.max())
            altos = np.flatnonzero(e25 >= top * 0.5)
            for p, q in zip(altos, altos[1:]):
                if q - p > 1 and float(e25[p:q].min()) <= min(float(e25[p]), float(e25[q])) * 0.316:
                    fallos.append('doble')
                    break
    # clic suelto: una muestra cuya 2.ª diferencia es enorme frente a su entorno de 5 ms (fuera del ataque)
    d2 = np.abs(np.diff(x, n=2, axis=1)).max(axis=0)
    if d2.size > 600:
        k = int(sr * 0.005)
        media = np.convolve(d2, np.ones(k) / k, 'same') + 1e-9
        ini = int(np.argmax(m > pk * 0.03)) + int(sr * 0.015)
        sospechas = np.flatnonzero((d2 > 60 * media) & (d2 > pk * 0.2))
        if sospechas[sospechas > ini].size:
            fallos.append('clic')
    # resonancia metálica (peine) en la cola de los sonidos no tonales
    if pool not in TONALES:
        i = int(np.argmax(m)) + int(0.05 * sr)
        cola = x[:, i:i + sr].mean(axis=0)
        if cola.size >= 4096 and float(np.abs(cola).max()) > pk * 0.01:
            mag = np.abs(np.fft.rfft(cola * np.hanning(cola.size)))
            f = np.fft.rfftfreq(cola.size, 1.0 / sr)
            lm = np.log(mag[(f >= 200) & (f <= 8000)] + 1e-12)
            mad = float(np.median(np.abs(lm - np.median(lm)))) * 1.4826 or 1.0
            if (float(lm.max()) - float(np.median(lm))) / mad > 15.0:
                fallos.append('resonancia')
    return fallos


_AUD = {}


def _cache_aud():
    import director_sonido_estado as E
    return E.CARPETA / 'cache' / 'oido_auditoria.json'


def _aud():
    if 'd' not in _AUD:
        import archivos_seguros
        d = archivos_seguros.leer_json(_cache_aud(), None)
        _AUD['d'] = d if isinstance(d, dict) and d.get('v') == AUDIT_VERSION else {'v': AUDIT_VERSION, 'archivos': {}}
    return _AUD['d']


def _guardar_aud():
    try:
        import archivos_seguros
        archivos_seguros.escribir_json(_cache_aud(), _aud())
    except Exception:
        pass


def fallos_de(lib, rel, pool=None, medir=True):
    """Los fallos de un archivo de la biblioteca (en caché por tamaño y fecha). None si no se pudo leer."""
    ruta = Path(lib) / rel
    try:
        st = ruta.stat()
    except OSError:
        return None
    firma = f'{st.st_size}|{int(st.st_mtime)}|{pool or ""}'
    d = _aud()['archivos']
    k = str(ruta)
    if k in d and d[k].get('firma') == firma:
        return d[k]['fallos']
    if not medir:
        return None
    try:
        import sonido_skill as S
        f = auditar(S.leer_audio(ruta), pool)
    except Exception:
        return None
    d[k] = {'firma': firma, 'fallos': f}
    return f


def filtrar_pools(pools, lib, cat=None, por_pool=4):
    """Los pools sin los archivos con fallos GRAVES, revisando por orden hasta tener `por_pool` limpios (lo que el Elector usa). Un pool que
    se quedaría vacío conserva su lista. Nunca lanza."""
    try:
        nuevos, fuera = {}, []
        for pool, lista in pools.items():
            limpios, malos = [], []
            for r in lista:
                if len(limpios) >= por_pool:
                    limpios.append(r)                       # el resto, sin medir (el Elector solo usa los primeros)
                    continue
                f = fallos_de(lib, r, pool) or []
                (malos if any(x in GRAVES for x in f) else limpios).append(r)
            nuevos[pool] = limpios or lista
            if limpios:
                fuera += [(pool, r) for r in malos]
        _guardar_aud()
        if fuera:
            log(f"{len(fuera)} archivo(s) fuera por fallos graves: " + ', '.join(Path(r).stem for _p, r in fuera[:6]))
        return nuevos
    except Exception:
        return pools


def auditar_biblioteca(lib, pools):
    """Todo lo de los pools (herramienta / prueba): {archivo: fallos} solo los que tienen alguno."""
    out = {}
    for pool, lista in pools.items():
        for r in lista:
            f = fallos_de(lib, r, pool)
            if f:
                out[r] = f
    _guardar_aud()
    return out


def reparar(x, fallos):
    """Lo arreglable al hornear: DC fuera (los fundidos los pone hornear)."""
    if fallos and 'dc' in fallos and x.size:
        x = x - x.mean(axis=1, keepdims=True)
    return x


# ============================================================================================ escuchar la mezcla (la página)
def _firma_plan(eventos, musica):
    base = [(e.get('archivo'), e.get('ini'), e.get('dur')) for e in eventos or []] + [(m.get('archivo'), m.get('dur')) for m in musica or []]
    try:
        base += [int(Path(str(e.get('archivo'))).stat().st_mtime) for e in (eventos or []) + (musica or []) if e.get('archivo')]
    except OSError:
        pass
    return hashlib.sha1(json.dumps(base, default=str).encode()).hexdigest()[:16]


def _sync_en_wav(e, pool):
    """Segundos dentro del WAV donde está su punto de sync: lo que APARECE, su primer sonido audible (−30 dB); lo que sube, el que guardó hornear."""
    import sonido_skill as S
    if pool in S.SYNC_CATALOGO and e.get('pico') is not None:
        return float(e['pico'])
    try:
        x = S.leer_audio(e['archivo'])
    except Exception:
        return None
    m = np.abs(x).max(axis=0) if x.size else np.zeros(0)
    if not m.size or m.max() <= 0:
        return None
    return float(np.argmax(m > m.max() * S.UMBRAL_INICIO)) / SR


def _mm_ss(t):
    t = max(0.0, float(t))
    return f'{int(t // 60)}:{int(t % 60):02d}'


ONDA_CUADROS = (-4, 12)            # la ventana de «cuadro a cuadro» de la página (cuadros respecto al 1.º de la animación)
ONDA_PASO = 0.004
OIDO_VERSION = 2


def _onda_cuadros(y, ini, ancla, fps):
    """La onda (pico por tramo de 4 ms, 0–1) del sonido colocado en `ini`, en la ventana ONDA_CUADROS alrededor de `ancla`."""
    if y is None or not y.size:
        return []
    m = np.abs(y).max(axis=0)
    pk = float(m.max()) or 1.0
    w0 = ancla + ONDA_CUADROS[0] / fps
    n = int(round((ONDA_CUADROS[1] - ONDA_CUADROS[0]) / fps / ONDA_PASO))
    paso = int(ONDA_PASO * SR)
    out = []
    for k in range(n):
        a = int(round((w0 + k * ONDA_PASO - ini) * SR))
        b = a + paso
        out.append(round(float(m[max(0, a):b].max()) / pk, 2) if b > 0 and a < m.size else 0.0)
    return out


def escuchar(video, forzar=False):
    """(En un hilo) la mezcla del diseño actual medida como la oiría earshot. Queda en caché en la carpeta del video ('oido.json').
    {'mezcla': {'lufs', 'tp_db', 'lra'}, 'sonidos': [{'i', 'segundo', 'estado': verde|ambar|rojo, 'error_ms', 'sobre_voz_db', 'sobre_musica_db',
    'nota'}], 'veredicto', 'nivel': 0|1|2, 'acciones': [{'i', 'segundo', 'texto', 'arreglo'}], 'cuenta': {...}}. None si no hay diseño."""
    import archivos_seguros
    import director_sonido as D
    import director_sonido_estado as E
    import director_sonido_mezcla as MZ
    estado = E.cargar(video)
    s = estado.get('sonido_skill') or {}
    eventos, musica = list(estado.get('sfx_plan') or []), list(estado.get('music_plan') or [])
    filas = list(s.get('filas') or [])
    if not eventos:
        return None
    firma = _firma_plan(eventos, musica)
    cache = E.carpeta_de(video) / 'oido.json'
    if not forzar:
        d = archivos_seguros.leer_json(cache, None)
        if isinstance(d, dict) and d.get('firma') == firma and d.get('version') == OIDO_VERSION:
            return d
    t0 = time.time()
    ctx = D.cargar_contexto(video) or {'video': video, 'palabras': []}
    fps = float(s.get('fps') or 0) or None
    para_medir = [dict(e, ancla=(e.get('ai') or {}).get('ancla'), ai=dict(e.get('ai') or {}, clave=f's{i}')) for i, e in enumerate(eventos)]
    med = MZ.medir(video, ctx, para_medir + [dict(m) for m in musica])
    cama = Cama.de_video(video, ctx, E.carpeta_de(video)) if ctx.get('palabras') else None
    # la música en el instante de cada SFX (¿lo tapa?)
    tira = None
    if musica and Path(str(musica[0].get('archivo') or '')).is_file():
        try:
            tira = MZ.Tira(musica[0]['archivo'])
        except Exception:
            tira = None
    sonidos, acciones = [], []
    cuadro = 1.0 / fps if fps else 1.0 / 30
    try:
        for i, e in enumerate(eventos):
            f = filas[i] if i < len(filas) else {}
            pool = f.get('pool') or ''
            # contra el cuadro de SU animación ('visual' no cambia al moverlo a mano), no contra donde quedó
            ancla = float(f.get('visual', f.get('segundo')) if f else (e.get('ai') or {}).get('ancla') or 0.0)
            sync = _sync_en_wav(e, pool)
            ini = float(e.get('ini') or 0.0)
            ini_real = round(ini * fps) / fps if fps else ini
            if sync is None:
                err = None
            else:
                err = (ini_real + sync) - (ancla + OFFSET_MS.get(pool, 0) / 1000.0)
                if float(e.get('dur') or 0) <= 0.06 and ini <= 0.0:
                    err = None                                  # se quedó sin sonido al recortarlo antes del 0
            # cuánto se oye: su sonoridad K (donde suena, −20 dB de su pico) frente a la voz de la FRASE (no la del instante: un pop al
            # empezar una palabra no la pisa) y frente a la música en esas mismas muestras
            sobre_voz = sobre_mus = None
            env = []
            try:
                y = _leer(e['archivo'])
                env = _onda_cuadros(y, ini_real, ancla, fps or 30.0)
                if y is not None and y.shape[1]:
                    act = np.abs(y).max(axis=0) > np.abs(y).max() * 0.1
                    if act.sum() > SR * 0.01:
                        l_sfx = lufs(y[:, act])
                        v = cama.frase(ancla) if cama is not None else None
                        sobre_voz = round(l_sfx - v, 1) if v is not None else None
                        if tira is not None:
                            mu = tira.leer(int(round(ini_real * SR)), y.shape[1])
                            sobre_mus = round(l_sfx - lufs(mu[:, act]), 1)
            except Exception:
                pass
            nota, estado_s = '', 'verde'
            if err is None:
                estado_s, nota = 'rojo', 'sin sonido'
            elif abs(err) > VERDE_MS / 1000.0:
                estado_s, nota = 'rojo', f"{abs(err) * 1000:.0f} ms {'tarde' if err > 0 else 'antes'}"
            elif abs(err) > cuadro + 0.002:
                estado_s, nota = 'ambar', f"{abs(err) * 1000:.0f} ms {'tarde' if err > 0 else 'antes'}"
            if sobre_voz is not None and sobre_voz > PISA_VOZ_DB:
                estado_s = 'rojo' if estado_s == 'rojo' else 'ambar'
                nota = (nota + ' · ' if nota else '') + 'pisa la voz'
            if pool in TEXTURAS:
                sobre_mus = None if sobre_mus is not None and sobre_mus < TAPADO_DB else sobre_mus
            if sobre_mus is not None and sobre_mus < TAPADO_DB:
                estado_s = 'rojo' if estado_s == 'rojo' else 'ambar'
                nota = (nota + ' · ' if nota else '') + 'tapado por la música'
            off_ms = float(OFFSET_MS.get(pool, 0))
            sonidos.append({'i': i, 'segundo': round(ancla, 3), 'pool': pool, 'tipo': f.get('tipo'), 'estado': estado_s, 'nota': nota,
                            'error_ms': None if err is None else round(err * 1000, 1), 'sobre_voz_db': sobre_voz, 'sobre_musica_db': sobre_mus,
                            # para «cuadro a cuadro» de la página: cuándo suena frente al 1.er cuadro de su animación, dónde debía y su onda
                            'suena_ms': None if err is None else round(err * 1000 + off_ms, 1), 'esperado_ms': off_ms, 'onda': env})
            nombre = (f.get('tipo') or pool or 'sonido').replace('_', ' ')
            base = {'i': i, 'segundo': ancla, 'tiempo': _mm_ss(ancla), 'tipo': f.get('tipo') or pool, 'estado': estado_s}
            if err is not None and abs(err) > cuadro + 0.002:
                acciones.append(dict(base, peso=abs(err) * 1000, que='tarde' if err > 0 else 'antes', ms=round(abs(err) * 1000),
                                     texto=f"{_mm_ss(ancla)} «{nombre}» suena {abs(err) * 1000:.0f} ms {'tarde' if err > 0 else 'antes'} → ponerlo en su cuadro",
                                     arreglo={'accion': 'mover', 'valor': round(-err, 3)}))
            if sobre_voz is not None and sobre_voz > PISA_VOZ_DB:
                baja = round(min(9.0, sobre_voz - PISA_VOZ_DB + 4.0), 1)
                acciones.append(dict(base, peso=200 + sobre_voz, que='pisa', db=-baja,
                                     texto=f"{_mm_ss(ancla)} «{nombre}» pisa la voz → bajarlo {baja:g} dB", arreglo={'accion': 'nivel', 'valor': -baja}))
            elif sobre_mus is not None and sobre_mus < TAPADO_DB:
                sube = round(min(6.0, TAPADO_DB - sobre_mus + 2.0), 1)
                acciones.append(dict(base, peso=150 - sobre_mus, que='tapado', db=sube,
                                     texto=f"{_mm_ss(ancla)} «{nombre}» queda tapado por la música → subirlo {sube:g} dB",
                                     arreglo={'accion': 'nivel', 'valor': sube}))
    finally:
        if tira is not None:
            tira.cerrar()
    # amontonados: dos sonidos más juntos que la separación mínima de su tipo (y que no sean una ráfaga a propósito)
    for a, b in zip(filas, filas[1:]):
        dt = float(b['segundo']) - float(a['segundo'])
        minimo = RAFAGA_MS.get(b.get('pool'), 250) / 1000.0 if a.get('pool') == b.get('pool') else 0.25
        if 0 <= dt < minimo:
            acciones.append({'i': filas.index(b), 'segundo': float(b['segundo']), 'tiempo': _mm_ss(b['segundo']), 'tipo': b.get('tipo'),
                             'estado': 'ambar', 'peso': 120, 'que': 'juntos', 'ms': round(dt * 1000),
                             'texto': f"{_mm_ss(b['segundo'])} dos sonidos a {dt * 1000:.0f} ms → quitar el segundo",
                             'arreglo': {'accion': 'quitar'}})
    mz = med.get('mezcla') or {}
    tp, lu, lra = mz.get('tp_db'), mz.get('lufs'), mz.get('lra')
    tp_voz = (med.get('voz') or {}).get('tp_db')
    if tp is not None and tp > TP_TECHO:
        de_origen = tp_voz is not None and tp_voz > TP_TECHO
        acciones.append({'i': None, 'segundo': None, 'peso': 300, 'arreglo': None, 'estado': 'rojo', 'que': 'pico_video' if de_origen else 'pico',
                         'db': round(tp, 1),
                         'texto': (f"el audio del video ya llega a {tp_voz:+.1f} dBTP (pico de la mezcla {tp:+.1f}) → al exportar, limita a −1 dBTP"
                                   if de_origen else f"los sonidos llevan el pico de la mezcla a {tp:+.1f} dBTP → al exportar, limita a −1 dBTP")})
    if lu is not None and not LUFS_WEB[0] <= lu <= LUFS_WEB[1]:
        acciones.append({'i': None, 'segundo': None, 'peso': 50, 'estado': 'ambar', 'que': 'volumen', 'db': round(lu, 1),
                         'texto': f"la mezcla está a {lu:.1f} LUFS → al exportar, normaliza a −14 LUFS (redes)", 'arreglo': None})
    cuenta = {k: sum(1 for x in sonidos if x['estado'] == k) for k in ('verde', 'ambar', 'rojo')}
    graves = cuenta['rojo'] + (1 if tp is not None and tp > TP_TECHO else 0) + int((med.get('clipping') or 0) > 0)
    nivel = 0 if graves == 0 and cuenta['ambar'] <= max(1, len(sonidos) // 10) else (1 if graves <= 2 else 2)
    acciones.sort(key=lambda a: -a['peso'])
    for a in acciones:
        a.pop('peso', None)
    d = {'firma': firma, 'version': OIDO_VERSION, 'fecha': time.strftime('%Y-%m-%d %H:%M:%S'), 'segundos': round(time.time() - t0, 2),
         'mezcla': {'lufs': lu, 'tp_db': tp, 'lra': lra, 'clipping': int(med.get('clipping') or 0)},
         'musica_bajo_voz_db': med.get('musica_bajo_voz_db'), 'sonidos': sonidos, 'cuenta': cuenta,
         'nivel': nivel, 'veredicto': VEREDICTOS[nivel], 'acciones': acciones, 'fps': fps}
    try:
        archivos_seguros.escribir_json(cache, d)
    except Exception:
        pass
    log(f"{VEREDICTOS[nivel]} · {cuenta['verde']} en su cuadro, {cuenta['ambar']} ámbar, {cuenta['rojo']} rojo · "
        + (f'{lu:.1f} LUFS · ' if lu is not None else '') + (f'{tp:+.1f} dBTP' if tp is not None else '') + f' · {d["segundos"]} s')
    return d


def _leer(ruta):
    import sonido_skill as S
    try:
        return S.leer_audio(ruta)
    except Exception:
        return None


def arreglar(video, solo=None):
    """Aplica las acciones con arreglo (mover / nivel / quitar) de la última escucha, en UNA sola horneada. (ok, texto)."""
    import director_sonido_estado as E
    import sonido_skill as S
    d = escuchar(video)
    if not d:
        return False, 'No hay sonido diseñado para este video.'
    acc = [a for a in d.get('acciones') or [] if a.get('arreglo') and a.get('i') is not None and (solo is None or a['i'] in solo)]
    if not acc:
        return True, 'Nada que arreglar.'
    estado = E.cargar(video)
    s = estado.get('sonido_skill') or {}
    filas = [dict(f) for f in s.get('filas') or []]
    quitar = set()
    for a in acc:
        i, ar = a['i'], a['arreglo']
        if not 0 <= i < len(filas):
            continue
        if ar['accion'] == 'mover':
            filas[i]['segundo'] = round(max(0.0, float(filas[i]['segundo']) + float(ar['valor'])), 3)
        elif ar['accion'] == 'nivel':
            filas[i]['ganancia_db'] = round(float(filas[i].get('ganancia_db') or 0.0) + float(ar['valor']), 1)
        elif ar['accion'] == 'quitar':
            quitar.add(i)
    filas = sorted((f for k, f in enumerate(filas) if k not in quitar), key=lambda f: f['segundo'])
    ok, texto = S.rehornear(video, filas)
    return ok, (f'{len(acc)} arreglo(s) aplicados · ' + texto) if ok else texto
