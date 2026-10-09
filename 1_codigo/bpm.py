# CineCaptions · By Cinema Productions
# 1_codigo/bpm.py — detección de BPM y de los golpes de pulso de una música (v5.4.8), solo con numpy.
"""
    detectar(ruta, max_s=90)  -> {'bpm', 'confianza', 'beats': [t…], 'periodo', 'fase'} | None

Método: se decodifica a mono 11 kHz (PyAV), se saca la envolvente de «novedad» (flujo espectral con paso de 11,6 ms) y se busca el periodo con la autocorrelación entre
60 y 180 BPM (con un sesgo suave hacia 70-140 para no confundir el pulso con su doble o su mitad). Los golpes se colocan con la fase que mejor encaja con la envolvente. Sirve
para elegir la música de una carpeta que más se parece al ritmo que se quiere, alinear su pulso con el golpe de la palabra clave y acercar los efectos a los tiempos fuertes.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

TASA = 11025
PASO = 128                                  # muestras por cuadro de la envolvente (11,6 ms)
CACHE = Path.home() / 'DaVinciSubtitles' / 'bpm_cache.json'


def _decodificar(ruta, max_s=90.0):
    import av
    import numpy as np
    salida = []
    total = 0
    with av.open(str(ruta)) as c:
        flujo = c.streams.audio[0]
        r = av.AudioResampler(format='fltp', layout='mono', rate=TASA)
        for fr in c.decode(flujo):
            for x in r.resample(fr):
                a = x.to_ndarray().reshape(-1)
                salida.append(a)
                total += len(a)
            if total >= max_s * TASA:
                break
    return (np.concatenate(salida) if salida else np.zeros(0, np.float32)).astype(np.float32)


def _novedad(audio):
    """Envolvente de novedad (flujo espectral positivo) con un valor cada PASO muestras."""
    import numpy as np
    n_fft = 512
    if len(audio) < n_fft * 4:
        return np.zeros(0, np.float32)
    ventana = np.hanning(n_fft).astype(np.float32)
    n = (len(audio) - n_fft) // PASO
    idx = np.arange(n_fft)[None, :] + PASO * np.arange(n)[:, None]
    marcos = audio[idx] * ventana
    mag = np.abs(np.fft.rfft(marcos, axis=1)).astype(np.float32)
    mag = np.log1p(mag * 10.0)
    dif = np.maximum(0.0, np.diff(mag, axis=0))
    flujo = dif.sum(axis=1) + 4.0 * dif[:, :12].sum(axis=1)                    # los graves (bombo, bajo) pesan más: marcan el tiempo fuerte mejor que los platillos
    flujo = flujo - np.convolve(flujo, np.ones(43) / 43.0, mode='same')          # quita la tendencia (~0,5 s)
    return np.maximum(flujo, 0.0).astype(np.float32)


def detectar_de_audio(audio):
    import numpy as np
    env = _novedad(audio)
    if len(env) < 200:
        return None
    fps = TASA / float(PASO)
    env = env / (env.max() + 1e-9)
    n = len(env)
    lag_min, lag_max = int(fps * 60.0 / 180.0), int(fps * 60.0 / 60.0)
    f = np.fft.rfft(env - env.mean(), 2 * n)
    ac = np.fft.irfft(f * np.conj(f))[:lag_max + 2]
    ac = ac / (ac[0] + 1e-9)
    mejor, mejor_p = None, -1.0
    for lag in range(lag_min, min(lag_max, len(ac) - 1)):
        bpm = 60.0 * fps / lag
        sesgo = 1.0 if 70.0 <= bpm <= 140.0 else 0.82                              # los pulsos de 70-140 son los más habituales
        # se premia que el doble y la mitad también encajen (un pulso de verdad se repite en sus múltiplos)
        extra = 0.0
        for m in (2, 3):
            if lag * m < len(ac):
                extra += 0.35 * ac[lag * m] / m
        p = (ac[lag] + extra) * sesgo
        if p > mejor_p:
            mejor_p, mejor = p, lag
    if mejor is None:
        return None
    # afinar el periodo a una fracción de cuadro con una parábola alrededor del máximo
    l0 = mejor
    if 1 <= l0 < len(ac) - 1:
        a, b, c = ac[l0 - 1], ac[l0], ac[l0 + 1]
        den = a - 2 * b + c
        if abs(den) > 1e-9:
            l0 = l0 + 0.5 * (a - c) / den
    periodo = l0 / fps
    # fase: el desplazamiento (en cuadros) con más energía en los golpes
    ks = np.arange(int((n - 1) / l0))
    mejor_fase, mejor_e = 0.0, -1.0
    for fase in np.arange(0.0, l0, 0.5):                                 # peine de golpes con el periodo FRACCIONARIO (con un paso entero la fase se escapa en 40 s)
        idx = np.round(fase + ks * l0).astype(int)
        idx = idx[idx < n]
        e = float(env[idx].sum())
        if e > mejor_e:
            mejor_e, mejor_fase = e, float(fase)
    t0 = mejor_fase / fps
    duracion = len(audio) / float(TASA)
    beats = []
    t = t0
    while t < duracion:
        beats.append(round(t, 3))
        t += periodo
    confianza = float(max(0.0, min(1.0, mejor_p)))
    return {'bpm': round(60.0 / periodo, 1), 'confianza': round(confianza, 3), 'beats': beats, 'periodo': round(periodo, 4), 'fase': round(t0, 4)}


def _huella(ruta):
    p = Path(ruta)
    return hashlib.sha1(f'{p.resolve()}|{p.stat().st_mtime_ns}|{p.stat().st_size}'.encode('utf-8')).hexdigest()[:16]


def detectar(ruta, max_s=90.0, usar_cache=True):
    """El BPM y el pulso de una música (la caché guarda solo bpm/periodo/fase: los golpes se recalculan según la duración que se pida)."""
    ruta = Path(ruta)
    try:
        h = _huella(ruta)
        datos = {}
        if usar_cache:
            try:
                datos = json.loads(CACHE.read_text(encoding='utf-8'))
            except Exception:
                datos = {}
            g = datos.get(h)
            if g:
                return g
        audio = _decodificar(ruta, max_s)
        r = detectar_de_audio(audio)
        if r and usar_cache:
            datos[h] = r
            if len(datos) > 400:
                for k in list(datos)[:100]:
                    datos.pop(k, None)
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            CACHE.write_text(json.dumps(datos), encoding='utf-8')
        return r
    except Exception:
        return None


def golpes_hasta(info, duracion, desplazamiento=0.0):
    """Los golpes de pulso (s) hasta `duracion`, sobre la línea de tiempo cuando la música empieza `desplazamiento` s DENTRO del archivo (los anteriores se descartan)."""
    if not info:
        return []
    p, f = float(info['periodo']), float(info['fase'])
    salida = []
    k = 0
    while True:
        t = f + k * p - desplazamiento
        if t > duracion:
            break
        if t >= 0:
            salida.append(round(t, 3))
        k += 1
    return salida


def desplazamiento_para(info, t_objetivo):
    """Cuántos segundos hay que empezar DENTRO del archivo para que un golpe de pulso caiga en `t_objetivo` de la línea de tiempo (0 ≤ resultado < periodo)."""
    if not info:
        return 0.0
    p, f = float(info['periodo']), float(info['fase'])
    return (f - float(t_objetivo)) % p


def acercar_al_pulso(tiempos, golpes, tolerancia=0.15):
    """Cada tiempo se mueve al golpe de pulso más cercano si está a menos de `tolerancia` s (si no, se queda)."""
    if not golpes:
        return list(tiempos)
    salida = []
    for t in tiempos:
        g = min(golpes, key=lambda x: abs(x - t))
        salida.append(g if abs(g - t) <= tolerancia else t)
    return salida
