# CineCaptions · By Cinema Productions
# 1_codigo/director_sonido_sintesis.py — «AI Sound Director»: sonido PROCEDURAL diseñado alrededor de cada movimiento (no un WAV genérico).
"""
Cada sonido se CALCULA con los datos del motion que lo pide (duración, easing, dirección, velocidad, tamaño) y la paleta del proyecto (brillo,
peso, transitorios, estéreo, reverb): un héroe que entra con easeOutBack en 10 fotogramas suena distinto de una cinta que gira en 9 o de un anillo que
se dibuja en 0,45 s frenando. Solo numpy (+ los filtros de ffmpeg de PyAV para los fijos): sin dependencias nuevas. Todo a 48 kHz, estéreo (2, n).

    whoosh(dur, direccion, easing, brillo, peso)   ruido rosa con un paso banda que se mueve con la VELOCIDAD del easing (rápido = brillante),
                                                   cuerpo grave según el tamaño, aire arriba, paneo que sigue la POSICIÓN del movimiento
    golpe(peso, brillo, cola, pre)                 clic + golpe 120–500 Hz + sub que cae 55→38 Hz + cola corta; `pre` = el «slam» de aire que llega a él
    tick(brillo) · pop(brillo)                     interfaz: un tono corto con su clic / un pop que cae de tono
    trazo(dur, potencia, brillo)                   rotulador que dibuja (ruido 1,5–4,5 kHz con vibración de trazo) con la energía de 1 − (1 − p)^potencia
    giro(dur, brillo)                              whoosh que da vuelta en estéreo + el «slap» final de la cinta
    riser(dur, brillo)                             sube (ruido con el filtro abriéndose + dos tonos que suben) y se corta justo antes del golpe
    acento(nota, dur, brillo)                      campana suave (parciales inarmónicos con caídas distintas) para datos y cierre: un MOTIVO del video
    easing(nombre, p) / velocidad(nombre, p)       easeOutBack (el «pop» del Tema 1), easeOutExpo, easeInExpo, easeInOutCubic, easeOutPow, linear
"""
import numpy as np

SR = 48000
_FRAME, _HOP = 1024, 256


# ------------------------------------------------------------------------------------------------------------------------------ easing
def easing(nombre, p, k=2.4):
    p = np.clip(np.asarray(p, dtype=np.float64), 0.0, 1.0)
    if nombre == 'easeOutBack':                       # el de los macros del Tema 1 (kinetic_elementos._rebote)
        q = p - 1.0
        return 1.0 + 2.70158 * q ** 3 + 1.70158 * q ** 2
    if nombre == 'easeOutExpo':
        return np.where(p >= 1.0, 1.0, 1.0 - 2.0 ** (-10.0 * p))
    if nombre == 'easeInExpo':
        return np.where(p <= 0.0, 0.0, 2.0 ** (10.0 * p - 10.0))
    if nombre == 'easeInOutCubic':
        return np.where(p < 0.5, 4 * p ** 3, 1 - (-2 * p + 2) ** 3 / 2)
    if nombre == 'easeOutPow':                        # el trazo del anillo: 1 − (1 − p)^k
        return 1.0 - (1.0 - p) ** k
    return p


def velocidad(nombre, p, k=2.4):
    """|de/dp| normalizada a 1 (la energía del movimiento en cada instante; diferencia centrada, fuera de 0–1 vale 0)."""
    p = np.asarray(p, dtype=np.float64)
    h = 1e-3
    d = np.abs(easing(nombre, np.clip(p + h, 0, 1), k) - easing(nombre, np.clip(p - h, 0, 1), k)) / (2 * h)
    d = np.where((p < 0) | (p > 1), 0.0, d)
    return d / max(1e-9, float(d.max())) if d.size else d


# ------------------------------------------------------------------------------------------------------------------------------ piezas
def _rng(rng):
    return rng if rng is not None else np.random.default_rng(1)


def _rosa(n, rng):
    X = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1.0 / SR)
    X[1:] /= np.sqrt(f[1:])
    X[0] = 0
    y = np.fft.irfft(X, n)
    return y / max(1e-12, np.sqrt(np.mean(y ** 2)))


def _banda_movil(x, fc, ancho_oct=1.0, piso=0.0):
    """Paso banda gaussiano (en octavas) cuyo centro `fc` (Hz, uno por marco o uno fijo) se mueve en el tiempo. STFT con solapamiento 75 %."""
    n = x.size
    pad = np.concatenate((np.zeros(_FRAME), x, np.zeros(_FRAME)))
    w = np.hanning(_FRAME)
    marcos = 1 + (pad.size - _FRAME) // _HOP
    idx = np.arange(_FRAME)[None, :] + _HOP * np.arange(marcos)[:, None]
    X = np.fft.rfft(pad[idx] * w, axis=1)
    f = np.maximum(np.fft.rfftfreq(_FRAME, 1.0 / SR), 1.0)
    fc = np.broadcast_to(np.asarray(fc, dtype=np.float64), (marcos,)) if np.ndim(fc) == 0 else np.interp(np.arange(marcos), np.linspace(0, marcos - 1, len(fc)), fc)
    g = np.exp(-0.5 * (np.log2(f[None, :] / np.maximum(fc[:, None], 20.0)) / max(0.05, ancho_oct)) ** 2)
    g = piso + (1 - piso) * g
    y = np.fft.irfft(X * g, n=_FRAME, axis=1) * w
    out = np.zeros(pad.size)
    for t in range(marcos):
        out[t * _HOP:t * _HOP + _FRAME] += y[t]
    out /= 1.5                                         # (Hann² con 75 % de solape suma 1,5)
    return out[_FRAME:_FRAME + n]


def _env(valores, n):
    """Una envolvente de `n` muestras desde puntos de control equiespaciados."""
    v = np.asarray(valores, dtype=np.float64)
    return np.interp(np.linspace(0, 1, n), np.linspace(0, 1, v.size), v)


def _pan(mono, pos, ancho=0.0):
    """Paneo de potencia constante (pos −1 izquierda … +1 derecha, uno por muestra o puntos de control) + un poco de Haas para dar anchura."""
    n = mono.size
    pos = _env(pos, n) if np.ndim(pos) else np.full(n, float(pos))
    a = (np.clip(pos, -1, 1) + 1) * np.pi / 4
    l, r = mono * np.cos(a), mono * np.sin(a)
    if ancho > 0:
        d = int(ancho * 0.0006 * SR)                   # hasta 0,6 ms de diferencia entre canales
        if d > 0:
            r = np.concatenate((np.zeros(d), r[:-d]))
    return np.vstack((l, r)).astype(np.float32)


def _normalizar(x, pico_db=-1.0):
    p = float(np.max(np.abs(x))) if x.size else 0.0
    return (x * (10 ** (pico_db / 20) / p)).astype(np.float32) if p > 0 else x.astype(np.float32)


def _fundido(x, entrada_s=0.003, salida_s=0.02):
    n = x.shape[-1]
    a, b = min(n, int(entrada_s * SR)), min(n, int(salida_s * SR))
    e = np.ones(n)
    if a:
        e[:a] = np.linspace(0, 1, a)
    if b:
        e[-b:] *= np.linspace(1, 0, b)
    return x * e


def _sol(f_ini, f_fin, n, curva=1.0):
    """Un seno que glisa de f_ini a f_fin (Hz)."""
    f = f_ini + (f_fin - f_ini) * np.linspace(0, 1, n) ** curva
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


# ------------------------------------------------------------------------------------------------------------------------------ sonidos
def whoosh(dur, direccion=0.0, easing_='easeOutExpo', brillo=0.5, peso=0.5, rng=None, cola=0.12):
    """El aire que mueve algo que pasa: la energía y el brillo siguen la VELOCIDAD del easing; el paneo, su POSICIÓN. `direccion` −1 (de derecha a
    izquierda) … +1 (de izquierda a derecha), 0 = de frente."""
    rng = _rng(rng)
    n = int((dur + cola) * SR)
    m = 64
    p = np.linspace(0, 1, m)
    act = p * (dur + cola) / max(dur, 1e-3)
    v = np.where(act <= 1.0, velocidad(easing_, np.minimum(act, 1.0)), np.exp(-(act - 1.0) * (dur / max(cola, 1e-3)) * 3.0))
    v = np.convolve(np.pad(v, (3, 3), mode='edge'), np.ones(7) / 7, 'valid')
    fc = 350.0 + (900.0 + 3200.0 * brillo) * v
    ruido = _rosa(n, rng)
    cuerpo = _banda_movil(ruido, fc, ancho_oct=1.1 + 0.4 * peso)
    aire = _banda_movil(_rosa(n, rng), 7000.0 + 4000 * brillo, ancho_oct=0.8) * 0.35 * brillo
    grave = _banda_movil(ruido, 120.0 + 60 * v.mean(), ancho_oct=0.9) * 0.6 * peso
    env = _env(v ** 0.9, n)
    mono = (cuerpo + aire + grave) * env
    pos = direccion * (easing(easing_, np.minimum(act, 1.0)) * 2 - 1) if direccion else np.zeros(m)
    return _normalizar(_fundido(_pan(mono, pos, ancho=0.4 + 0.6 * abs(direccion))))


def golpe(peso=0.7, brillo=0.5, cola=0.4, pre=0.0, rng=None):
    """El golpe de algo que llega (el «pop» del héroe). `pre` s de «slam» (aire que sube) antes del golpe, que cae en el instante `pre`."""
    rng = _rng(rng)
    largo = 0.12 + 0.55 * cola + 0.25 * peso
    n = int(largo * SR)
    t = np.arange(n) / SR
    clic = _banda_movil(rng.standard_normal(n), 4500.0 + 3000 * brillo, ancho_oct=1.4) * np.exp(-t / 0.0035)
    golpe_ = _banda_movil(rng.standard_normal(n), 260.0, ancho_oct=1.0) * np.exp(-t / (0.045 + 0.03 * peso))
    sub = _sol(56.0, 38.0, n, 0.6) * np.exp(-t / (0.12 + 0.18 * peso))
    tono = _sol(118.0, 82.0, n, 0.8) * np.exp(-t / 0.09)
    cola_ = _banda_movil(_rosa(n, rng), 900.0 + 900 * brillo, ancho_oct=1.8) * np.exp(-np.maximum(t - 0.02, 0) / (0.08 + 0.25 * cola)) * (t > 0.01)
    mono = 0.55 * clic * (0.6 + brillo) + 0.9 * golpe_ + (0.7 + 0.8 * peso) * sub + 0.35 * tono + 0.08 * cola * cola_
    x = _pan(_fundido(mono, 0.0005, 0.05), 0.0, ancho=0.2)
    if pre > 0:                                        # el aire que sube (easeIn: cada vez más rápido) hasta el instante del golpe
        s = whoosh(pre, 0.0, 'easeInExpo', brillo, peso * 0.6, rng, cola=0.0)[:, :int(pre * SR)] * 0.5
        y = np.zeros((2, s.shape[1] + x.shape[1]), np.float32)
        y[:, :s.shape[1]] = s
        y[:, s.shape[1]:] += x
        x = y
    return _normalizar(x)


def tick(brillo=0.5, rng=None):
    rng = _rng(rng)
    n = int(0.045 * SR)
    t = np.arange(n) / SR
    f = 1800.0 + 1400.0 * brillo
    mono = (np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * 2 * f * t)) * np.exp(-t / 0.010)
    mono += 0.3 * _banda_movil(rng.standard_normal(n), 6000.0, 1.0) * np.exp(-t / 0.0015)
    return _normalizar(_pan(_fundido(mono, 0.0003, 0.008), 0.0))


def pop(brillo=0.5, rng=None):
    n = int(0.08 * SR)
    t = np.arange(n) / SR
    mono = _sol(700.0 + 500 * brillo, 300.0, n, 0.5) * np.exp(-t / 0.022)
    return _normalizar(_pan(_fundido(mono, 0.0005, 0.01), 0.0))


def trazo(dur=0.45, potencia=2.4, brillo=0.5, rng=None):
    """El anillo que se dibuja (WriteOnEnd con frenada 1 − (1 − p)^potencia): rotulador sobre papel que va rápido y frena; el paneo da la vuelta."""
    rng = _rng(rng)
    n = int((dur + 0.05) * SR)
    m = 64
    p = np.linspace(0, 1, m)
    act = np.minimum(p * (dur + 0.05) / dur, 1.0)
    v = velocidad('easeOutPow', act, potencia) * (p * (dur + 0.05) <= dur + 1e-9)
    trama = 1 + 0.45 * np.sin(2 * np.pi * 19 * np.arange(n) / SR) * rng.uniform(0.7, 1.0)
    mono = _banda_movil(rng.standard_normal(n), 1800.0 + 2200 * brillo * _env(v, m), ancho_oct=0.9) * _env(v ** 0.8, n) * trama
    return _normalizar(_fundido(_pan(mono, np.sin(2 * np.pi * easing('easeOutPow', act, potencia)) * 0.45, ancho=0.5)))


def giro(dur=0.3, brillo=0.5, rng=None):
    """La cinta que entra girada y se asienta: whoosh que da vuelta en estéreo + el «slap» de la cinta al pegarse."""
    rng = _rng(rng)
    w = whoosh(dur, 0.0, 'easeOutBack', brillo, 0.3, rng, cola=0.05)
    n = w.shape[1]
    giro_pos = np.sin(np.linspace(0, 2 * np.pi, n)) * 0.6
    m = w.mean(axis=0)
    w = _pan(m, giro_pos, ancho=0.5)
    k = int(dur * 0.6 * SR)
    slap_n = int(0.06 * SR)
    t = np.arange(slap_n) / SR
    slap = _banda_movil(rng.standard_normal(slap_n), 1600.0, 1.2) * np.exp(-t / 0.012)
    w[:, k:k + slap_n] += _pan(slap * 0.6, 0.0)[:, :max(0, min(slap_n, n - k))]
    return _normalizar(w)


def riser(dur=1.4, brillo=0.5, hueco=0.03, rng=None):
    """Sube hasta el golpe: ruido con el filtro abriéndose (300 → 6000 Hz), dos tonos que suben y un corte limpio `hueco` s antes del final."""
    rng = _rng(rng)
    n = int(dur * SR)
    m = 64
    p = np.linspace(0, 1, m)
    fc = 300.0 * (20.0 * (0.5 + brillo)) ** (p ** 1.6)
    ruido = _banda_movil(_rosa(n, rng), fc, ancho_oct=1.3)
    tonos = 0.25 * (_sol(110.0, 440.0, n, 1.8) + _sol(111.5, 446.0, n, 1.8))
    env = _env(p ** 2.2, n)
    mono = (ruido + tonos) * env
    corte = int(hueco * SR)
    if corte:
        mono[-corte:] = 0.0
        mono[-corte - 240:-corte] *= np.linspace(1, 0, 240)
    return _normalizar(_pan(mono, np.linspace(-0.3, 0.3, 8), ancho=0.8))


def acento(nota=440.0, dur=1.2, brillo=0.5, rng=None):
    """Campana suave: parciales inarmónicos (1, 2,01, 3,0, 4,2) que caen a ritmos distintos, con un poco de vibrato y anchura."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    vib = 1 + 0.002 * np.sin(2 * np.pi * 5.0 * t)
    mono = np.zeros(n)
    for k, (r, a, tau) in enumerate(((1.0, 1.0, 0.55), (2.01, 0.45, 0.32), (3.0, 0.22 * (0.5 + brillo), 0.18), (4.2, 0.12 * brillo, 0.10))):
        mono += a * np.sin(2 * np.pi * nota * r * np.cumsum(vib) / SR) * np.exp(-t / (tau * dur))
    izq = _fundido(mono, 0.002, 0.08)
    der = _fundido(np.roll(mono, int(0.0004 * SR)) * 0.97, 0.002, 0.08)
    return _normalizar(np.vstack((izq, der)).astype(np.float32))


def rms_activo_db(x):
    """El nivel (dB) del tramo que suena (sin los silencios del final): para dejar cada sonido bajo la voz."""
    m = np.abs(x).max(axis=0) if x.ndim > 1 else np.abs(x)
    vivos = m > (m.max() * 0.05 if m.size else 0)
    y = x[:, vivos] if x.ndim > 1 else x[vivos]
    return float(10 * np.log10(np.mean(np.asarray(y, np.float64) ** 2) + 1e-12)) if y.size else -120.0
