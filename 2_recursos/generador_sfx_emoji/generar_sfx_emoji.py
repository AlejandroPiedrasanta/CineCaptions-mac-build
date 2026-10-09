# CineCaptions · By Cinema Productions
# 2_recursos/generador_sfx_emoji/generar_sfx_emoji.py — sintetiza (sin muestras de nadie: sin licencias) los sonidos de los emojis.
"""
Genera 2_recursos/sfx_emoji/<familia>.wav: un sonido corto por «familia» de emoji (fuego, beso, aplauso, dinero…).
1_codigo/emojis_sfx.py decide qué familia le toca a cada emoji; este script solo fabrica los audios.

    python generar_sfx_emoji.py                 # escribe en ../sfx_emoji
    python generar_sfx_emoji.py --solo fuego beso
    python generar_sfx_emoji.py --hoja hoja.png # además un espectrograma de cada sonido (para revisarlos de un vistazo)

Si existe reales/<familia>.wav (grabaciones CC0 elegidas; reales/FUENTES.json dice de dónde salió cada una) se usa ESA y no la síntesis.
El resto es síntesis con numpy (ruido filtrado, osciladores, formantes, Karplus-Strong): determinista (misma semilla = mismos audios)
y libre de derechos. Si el usuario prefiere grabaciones reales, basta con dejar un .wav con el MISMO nombre en
~/DaVinciSubtitles/sfx_emoji/: manda sobre el del programa.
"""
import argparse
import math
import json
import os
import shutil
import sys
import wave
import zlib

import numpy as np

SR = 44100
DEFECTO_SALIDA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'sfx_emoji')


# ------------------------------------------------------------------------------------------------ utilidades
def _n(d):
    return int(round(d * SR))


def tt(d):
    return np.arange(_n(d)) / SR


def silencio(d):
    return np.zeros(_n(d))


def ruido(d, r):
    return r.standard_normal(_n(d))


def _filtro(x, bajo=None, alto=None, pend=3):
    """Filtro en frecuencia (suave): 'bajo' = pasa-altos desde esa frecuencia; 'alto' = pasa-bajos hasta esa."""
    if len(x) < 8:
        return x
    X = np.fft.rfft(x)
    f = np.maximum(np.fft.rfftfreq(len(x), 1.0 / SR), 1e-6)
    H = np.ones_like(f)
    if bajo:
        H = H / np.sqrt(1.0 + (bajo / f) ** (2 * pend))
    if alto:
        H = H / np.sqrt(1.0 + (f / alto) ** (2 * pend))
    return np.fft.irfft(X * H, n=len(x))


def banda(x, f1, f2, pend=3):
    return _filtro(x, bajo=f1, alto=f2, pend=pend)


def bajos(x, fc, pend=3):
    return _filtro(x, alto=fc, pend=pend)


def altos(x, fc, pend=3):
    return _filtro(x, bajo=fc, pend=pend)


def env(d, ataque=0.003, tau=0.2, sost=0.0):
    """Ataque lineal + caída exponencial (tau). 'sost' = tramo plano antes de caer."""
    t = tt(d)
    e = np.minimum(t / max(ataque, 1e-4), 1.0)
    caida = np.exp(-np.maximum(t - ataque - sost, 0.0) / max(tau, 1e-4))
    return e * caida


def env_cos(d, sube=0.1, baja=0.3):
    """Campana suave: sube con coseno y baja con coseno (swells, whooshes)."""
    t = tt(d)
    e = np.ones_like(t)
    a = t < sube
    e[a] = 0.5 - 0.5 * np.cos(np.pi * t[a] / max(sube, 1e-4))
    b = t > d - baja
    e[b] = 0.5 + 0.5 * np.cos(np.pi * (t[b] - (d - baja)) / max(baja, 1e-4))
    return e


def osc(freq, d, forma='sin'):
    """Oscilador con frecuencia fija o por muestra (array). Formas: sin, saw, sq, tri."""
    n = _n(d)
    f = np.full(n, float(freq)) if np.isscalar(freq) else np.asarray(freq, dtype=float)
    if len(f) != n:
        f = np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(f)), f)
    ph = 2 * np.pi * np.cumsum(f) / SR
    if forma == 'sin':
        return np.sin(ph)
    u = (ph / (2 * np.pi)) % 1.0
    if forma == 'saw':
        return 2 * u - 1
    if forma == 'sq':
        return np.where(u < 0.5, 1.0, -1.0)
    if forma == 'tri':
        return 4 * np.abs(u - 0.5) - 1
    return np.sin(ph)


def glide(f0, f1, d, curva=1.0):
    t = np.linspace(0, 1, _n(d)) ** curva
    return f0 + (f1 - f0) * t


def glide_exp(f0, f1, d):
    t = np.linspace(0, 1, _n(d))
    return f0 * (f1 / f0) ** t


def poner(buf, x, t0, g=1.0):
    i = _n(t0)
    if i >= len(buf):
        return buf
    x = x[:len(buf) - i]
    buf[i:i + len(x)] += x * g
    return buf


def campana(f0, d, razones=(0.56, 0.92, 1.19, 1.71, 2.0, 2.74, 3.0, 3.76, 4.07), tau=0.6):
    t = tt(d)
    y = np.zeros_like(t)
    for i, r in enumerate(razones):
        y += (1.0 / (1 + i) ** 0.7) * np.sin(2 * np.pi * f0 * r * t) * np.exp(-t / (tau / (1 + 0.55 * i)))
    return y * np.minimum(t / 0.002, 1.0)


def ping(f, d=0.5, tau=0.18):
    t = tt(d)
    return (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t / (tau * 0.4))) * np.exp(-t / tau) * np.minimum(t / 0.001, 1)


def chime(f, d=0.8, tau=0.35):
    t = tt(d)
    return (np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * f * 2.0 * t) * np.exp(-t / (tau * 0.5))
            + 0.25 * np.sin(2 * np.pi * f * 3.01 * t) * np.exp(-t / (tau * 0.3))) * np.exp(-t / tau) * np.minimum(t / 0.002, 1)


def clic(r, d=0.012, f_alto=1500, g=1.0):
    return altos(ruido(d, r), f_alto) * env(d, 0.0005, d / 4) * g


def thump(f0=120, f1=45, d=0.25, tau=0.08):
    return np.sin(2 * np.pi * np.cumsum(glide_exp(f0, f1, d)) / SR) * env(d, 0.001, tau)


def ks(f, d, amort=0.996, r=None):
    """Karplus-Strong: cuerda pulsada."""
    n = _n(d)
    L = max(2, int(SR / f))
    buf = (r.uniform(-1, 1, L) if r is not None else np.random.uniform(-1, 1, L))
    out = np.zeros(n)
    for i in range(n):
        j = i % L
        out[i] = buf[j]
        buf[j] = amort * 0.5 * (buf[j] + buf[(j + 1) % L])
    return out


def formantes(src, fn, hop=512, ventana=1024):
    """Filtra 'src' con formantes que cambian en el tiempo. fn(t_seg) -> [(frecuencia, ancho, ganancia), …] (OLA con Hann)."""
    n = len(src)
    sal = np.zeros(n + ventana)
    w = np.hanning(ventana)
    f = np.fft.rfftfreq(ventana, 1.0 / SR)
    for ini in range(0, max(1, n - 1), hop):
        tr = src[ini:ini + ventana]
        if len(tr) < ventana:
            tr = np.pad(tr, (0, ventana - len(tr)))
        H = np.full_like(f, 0.04)
        for (F, bw, g) in fn((ini + ventana / 2) / SR):
            H += g / (1.0 + ((f - F) / (bw / 2.0)) ** 2)
        sal[ini:ini + ventana] += np.fft.irfft(np.fft.rfft(tr * w) * H, n=ventana) * w
    return sal[:n]


def mix(*xs):
    """Suma señales de distinta duración (rellena con silencio la más corta)."""
    n = max(len(x) for x in xs)
    y = np.zeros(n)
    for x in xs:
        y[:len(x)] += x
    return y


def normal(x, pico=0.85):
    m = np.max(np.abs(x)) if len(x) else 0
    return x * (pico / m) if m > 1e-9 else x


def fundido(x, entra=0.002, sale=0.02):
    x = x.copy()
    a, b = _n(entra), _n(sale)
    if a:
        x[:a] *= np.linspace(0, 1, a)
    if b:
        x[-b:] *= np.linspace(1, 0, b)
    return x


def eco(x, retardos=((0.07, 0.35), (0.13, 0.22), (0.21, 0.14)), cola=0.0):
    y = np.concatenate([x, np.zeros(_n(cola + max(r for r, _ in retardos)))])
    for r, g in retardos:
        i = _n(r)
        y[i:i + len(x)] += x * g
    return y


def vib(f, d, hz=5.5, prof=0.02, ret=0.0):
    t = tt(d)
    a = np.clip((t - ret) / 0.3, 0, 1)
    return f * (1 + prof * a * np.sin(2 * np.pi * hz * t))


# ------------------------------------------------------------------------------------------------ las familias
F = {}


def familia(f):
    F[f.__name__] = f
    return f


# ---- elementos y objetos ---------------------------------------------------------------
@familia
def fuego(r):
    D = 1.6
    buf = silencio(D)
    rug = bajos(ruido(D, r), 500) * (0.5 + 0.5 * np.abs(bajos(ruido(D, r), 6)) / (np.abs(bajos(ruido(D, r), 6)).max() + 1e-9))
    buf += rug * 1.6 * env_cos(D, 0.25, 0.5)
    ign = banda(ruido(0.5, r), 300, 2200) * env_cos(0.5, 0.12, 0.3) * 0.8
    poner(buf, ign, 0.0)
    for _ in range(46):
        t0 = r.uniform(0.05, 1.45)
        g = r.uniform(0.15, 1.0) * (1.0 - t0 / 2.2)
        poner(buf, altos(ruido(0.012, r), r.uniform(1200, 3500)) * env(0.012, 0.0004, r.uniform(0.002, 0.006)), t0, g)
    return buf


@familia
def beso(r):
    D = 0.5
    buf = silencio(D)
    pre = banda(ruido(0.1, r), 700, 2600) * env_cos(0.1, 0.05, 0.04) * 0.5
    poner(buf, pre, 0.0)
    sm = np.sin(2 * np.pi * np.cumsum(glide_exp(1100, 260, 0.09)) / SR) * env(0.09, 0.001, 0.025)
    poner(buf, sm * 0.9, 0.1)
    poner(buf, banda(ruido(0.03, r), 2500, 6500) * env(0.03, 0.0005, 0.008) * 0.8, 0.1)
    poner(buf, bajos(sm, 500) * 0.4, 0.108)
    return buf


@familia
def corazon(r):
    D = 1.25
    buf = silencio(D)
    for base in (0.0, 0.62):
        for dt, g in ((0.0, 1.0), (0.26, 0.75)):
            poner(buf, thump(70, 42, 0.28, 0.07) * g, base + dt)
            poner(buf, bajos(ruido(0.05, r), 250) * env(0.05, 0.001, 0.015) * 0.5 * g, base + dt)
    return buf


@familia
def dinero(r):
    D = 1.4
    buf = silencio(D)
    poner(buf, banda(ruido(0.04, r), 800, 5000) * env(0.04, 0.0008, 0.012) * 0.8, 0.0)
    poner(buf, thump(220, 120, 0.1, 0.03) * 0.6, 0.0)
    bell = (np.sin(2 * np.pi * 2093 * tt(1.0)) + 0.7 * np.sin(2 * np.pi * 3136 * tt(1.0)) + 0.4 * np.sin(2 * np.pi * 4186 * tt(1.0))) * env(1.0, 0.001, 0.38)
    poner(buf, bell * 0.8, 0.07)
    for k in range(9):
        poner(buf, ping(float(r.choice([2800, 3400, 4200, 5200, 6100])), 0.3, 0.07) * r.uniform(0.2, 0.5), 0.2 + k * 0.045 + r.uniform(0, 0.02))
    return buf


@familia
def aplauso(r):
    D = 1.7
    buf = silencio(D)
    cama = banda(ruido(D, r), 600, 3500) * env_cos(D, 0.3, 0.6) * 0.18
    buf += cama
    for _ in range(95):
        t0 = float(np.clip(r.normal(0.85, 0.42), 0.02, 1.55))
        poner(buf, banda(ruido(0.035, r), r.uniform(700, 1600), r.uniform(3000, 6000)) * env(0.035, 0.0006, r.uniform(0.006, 0.014)), t0, r.uniform(0.2, 1.0))
    return buf


@familia
def camara(r):
    D = 0.34
    buf = silencio(D)
    for t0, g in ((0.0, 1.0), (0.085, 0.65)):
        poner(buf, clic(r, 0.014, 900) * 1.0 * g, t0)
        poner(buf, thump(260, 120, 0.05, 0.012) * 0.8 * g, t0)
        poner(buf, np.sin(2 * np.pi * 1700 * tt(0.05)) * env(0.05, 0.0005, 0.012) * 0.25 * g, t0 + 0.003)
    poner(buf, banda(ruido(0.05, r), 3000, 7000) * env(0.05, 0.001, 0.02) * 0.2, 0.02)
    return buf


@familia
def campana_(r):
    return campana(587, 1.7, tau=0.9)


F['campana'] = F.pop('campana_')


@familia
def explosion(r):
    D = 2.0
    buf = silencio(D)
    poner(buf, thump(110, 28, 1.2, 0.35) * 1.2, 0.0)
    ru = ruido(D, r)
    barrido = bajos(ru, 2500) * env(D, 0.002, 0.45) + bajos(ru, 350) * env(D, 0.01, 0.9) * 1.2
    buf += barrido * 0.9
    poner(buf, clic(r, 0.02, 400) * 0.8, 0.0)
    return np.tanh(buf * 1.4)


@familia
def cohete(r):
    D = 1.6
    n = _n(D)
    ru = ruido(D, r)
    t = np.linspace(0, 1, n)
    y = np.zeros(n)
    pasos = 8
    for k in range(pasos):
        a, b = k * n // pasos, (k + 1) * n // pasos
        c = 250 * (14 ** (k / (pasos - 1)))
        trozo = ru[a:b + 600] if b + 600 <= n else ru[a:]
        y[a:b] = banda(trozo, c * 0.6, c * 1.5)[:b - a] * (1 + 2.5 * (k / pasos))
    y = y * env_cos(D, 0.6, 0.7)
    y += bajos(ruido(D, r), 180) * env_cos(D, 0.2, 0.9) * 2.2
    return y


@familia
def rayo(r):
    D = 0.9
    buf = silencio(D)
    for k in range(3):
        poner(buf, altos(ruido(0.03, r), 1500) * env(0.03, 0.0005, 0.01), k * 0.025, 0.8)
    zap = osc(glide_exp(4200, 140, 0.35), 0.35, 'saw') * env(0.35, 0.001, 0.12)
    poner(buf, zap * 0.7, 0.0)
    poner(buf, banda(ruido(0.5, r), 1200, 6000) * env(0.5, 0.0005, 0.12) * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 70 * tt(0.5)))), 0.02, 0.5)
    poner(buf, bajos(ruido(0.6, r), 220) * env(0.6, 0.02, 0.2) * 1.5, 0.1)
    return buf


@familia
def trueno(r):
    D = 2.0
    ru = bajos(ruido(D, r), 300)
    lento = np.abs(bajos(ruido(D, r), 5))
    lento = lento / (lento.max() + 1e-9)
    y = ru * (0.4 + 0.6 * lento) * env(D, 0.04, 0.8) * 3.0
    poner(y, clic(r, 0.05, 80), 0.0, 0.6)
    return y


@familia
def estrella(r):
    D = 1.3
    buf = silencio(D)
    notas = [1568, 1976, 2349, 2637, 3136, 3951, 4699]
    for k in range(11):
        f = float(r.choice(notas))
        poner(buf, ping(f, 0.45, 0.14) * (1.0 - k * 0.06), k * 0.085 + r.uniform(0, 0.02), 0.5)
    return buf


@familia
def magia(r):
    D = 1.6
    buf = silencio(D)
    esc = [523, 659, 784, 1047, 1319, 1568, 2093, 2637, 3136]
    for k, f in enumerate(esc):
        poner(buf, chime(float(f), 0.7, 0.22) * (0.5 + 0.05 * k), k * 0.07, 0.5)
    brillo = altos(ruido(1.2, r), 5000) * env_cos(1.2, 0.5, 0.6) * 0.12
    poner(buf, brillo, 0.1)
    for k in range(10):
        poner(buf, ping(float(r.uniform(3500, 7500)), 0.3, 0.08) * r.uniform(0.1, 0.3), 0.6 + k * 0.06)
    return buf


@familia
def burbuja(r):
    D = 0.2
    y = np.sin(2 * np.pi * np.cumsum(glide_exp(380, 1300, 0.07)) / SR) * env(0.07, 0.001, 0.03)
    buf = silencio(D)
    poner(buf, y, 0.0)
    poner(buf, clic(r, 0.004, 2000) * 0.2, 0.0)
    return buf


@familia
def fiesta(r):
    D = 1.6
    buf = silencio(D)
    poner(buf, bajos(ruido(0.05, r), 3500) * env(0.05, 0.0005, 0.012) * 1.0, 0.0)
    poner(buf, thump(220, 90, 0.12, 0.03) * 0.9, 0.0)
    cinta = altos(ruido(1.3, r), 3000) * env(1.3, 0.01, 0.3) * 0.25
    poner(buf, cinta, 0.03)
    for k in range(22):
        poner(buf, ping(float(r.choice([2093, 2637, 3136, 3951, 4699, 5274])), 0.3, 0.07) * r.uniform(0.15, 0.4), 0.05 + abs(r.normal(0.3, 0.3)))
    poner(buf, osc(glide_exp(900, 380, 0.5), 0.5, 'sin') * env(0.5, 0.01, 0.18) * 0.12, 0.06)
    return buf


def _bronce(f, d, vibr=0.0):
    fr = vib(f, d, 5.5, vibr, 0.1) if vibr else f
    s = osc(fr, d, 'saw') * 0.7 + osc(fr, d, 'sq') * 0.3
    return bajos(s, f * 4.5) * env_cos(d, 0.03, min(0.1, d / 2))


@familia
def fanfarria(r):
    D = 1.5
    buf = silencio(D)
    poner(buf, _bronce(523, 0.17), 0.0, 0.9)
    poner(buf, _bronce(784, 0.17), 0.18, 0.9)
    for f in (1047, 1319, 1568):
        poner(buf, _bronce(float(f), 0.95, 0.012), 0.38, 0.5)
    poner(buf, altos(ruido(1.0, r), 5000) * env(1.0, 0.01, 0.35) * 0.12, 0.38)
    return buf


@familia
def trompeta(r):
    D = 1.1
    buf = silencio(D)
    for k, f in enumerate((392, 523, 659, 784)):
        poner(buf, _bronce(float(f), 0.22 if k < 3 else 0.6, 0.01), k * 0.17, 0.8)
    return buf


@familia
def acierto(r):
    D = 0.7
    buf = silencio(D)
    poner(buf, chime(1319, 0.45, 0.16), 0.0, 0.8)
    poner(buf, chime(1760, 0.6, 0.25), 0.12, 0.9)
    return buf


@familia
def error(r):
    D = 0.8
    buf = silencio(D)
    for t0 in (0.0, 0.38):
        s = bajos(osc(118, 0.28, 'sq') + osc(124, 0.28, 'sq'), 900)
        poner(buf, s * env_cos(0.28, 0.01, 0.04), t0, 0.7)
    return buf


@familia
def alerta(r):
    D = 0.8
    buf = silencio(D)
    for k in range(4):
        poner(buf, bajos(osc(880 if k % 2 == 0 else 660, 0.16, 'sq'), 2500) * env_cos(0.16, 0.01, 0.03), k * 0.18, 0.55)
    return buf


@familia
def pregunta(r):
    D = 0.7
    buf = silencio(D)
    y = np.sin(2 * np.pi * np.cumsum(vib(glide(330, 700, 0.4), 0.4, 8, 0.03)) / SR) * env_cos(0.4, 0.05, 0.25)
    poner(buf, y, 0.0, 0.8)
    poner(buf, ping(1396, 0.3, 0.09), 0.38, 0.3)
    return buf


@familia
def exclamacion(r):
    D = 0.7
    buf = silencio(D)
    for k, f in enumerate((440, 880)):
        s = bajos(osc(f, 0.3, 'saw'), 3000) * env(0.3, 0.003, 0.08)
        poner(buf, s, k * 0.09, 0.7)
    poner(buf, thump(150, 70, 0.2, 0.05) * 0.6, 0.0)
    return buf


@familia
def gota(r):
    D = 0.5
    buf = silencio(D)
    y = np.sin(2 * np.pi * np.cumsum(glide_exp(520, 1500, 0.05)) / SR) * env(0.05, 0.0005, 0.02)
    poner(buf, y, 0.0, 0.9)
    poner(buf, np.sin(2 * np.pi * np.cumsum(glide_exp(480, 1300, 0.06)) / SR) * env(0.2, 0.0005, 0.07)[:_n(0.06)], 0.012, 0.3)
    poner(buf, eco(y, ((0.09, 0.3), (0.17, 0.15)))[:_n(0.4)], 0.0, 0.2)
    return buf


@familia
def salpicadura(r):
    D = 0.9
    buf = silencio(D)
    poner(buf, banda(ruido(0.6, r), 500, 6000) * env(0.6, 0.002, 0.15), 0.0, 0.8)
    for k in range(7):
        t0 = 0.05 + k * 0.07 + r.uniform(0, 0.03)
        poner(buf, np.sin(2 * np.pi * np.cumsum(glide_exp(float(r.uniform(400, 800)), float(r.uniform(1200, 2400)), 0.05)) / SR) * env(0.05, 0.0005, 0.02), t0, 0.35)
    return buf


@familia
def olas(r):
    D = 2.0
    y = banda(ruido(D, r), 150, 1800) * env_cos(D, 0.9, 0.9)
    y += altos(ruido(D, r), 2500) * env_cos(D, 1.0, 0.7) * 0.12
    return y


@familia
def lluvia(r):
    D = 1.7
    buf = silencio(D)
    buf += banda(ruido(D, r), 1500, 7000) * 0.07 * env_cos(D, 0.3, 0.5)
    for _ in range(120):
        poner(buf, np.sin(2 * np.pi * float(r.uniform(2500, 7000)) * tt(0.012)) * env(0.012, 0.0004, 0.003), r.uniform(0.0, 1.6), r.uniform(0.1, 0.5))
    return buf


@familia
def viento(r):
    D = 1.6
    n = _n(D)
    ru = ruido(D, r)
    y = np.zeros(n)
    pasos = 10
    for k in range(pasos):
        a, b = k * n // pasos, (k + 1) * n // pasos
        c = 500 + 700 * math.sin(math.pi * k / (pasos - 1))
        y[a:b] = banda(ru[a:b + 400] if b + 400 <= n else ru[a:], c * 0.5, c * 1.4)[:b - a]
    return y * env_cos(D, 0.5, 0.6) * 1.6


@familia
def fuegos_artificiales(r):
    D = 2.2
    buf = silencio(D)
    sil = np.sin(2 * np.pi * np.cumsum(glide(700, 2600, 0.6, 1.4)) / SR) * env_cos(0.6, 0.1, 0.1) * 0.25
    poner(buf, sil, 0.0)
    poner(buf, thump(100, 32, 0.9, 0.22) * 1.0, 0.62)
    poner(buf, banda(ruido(0.5, r), 300, 3500) * env(0.5, 0.001, 0.12) * 0.7, 0.62)
    for _ in range(80):
        t0 = 0.66 + abs(r.normal(0.0, 0.45))
        poner(buf, altos(ruido(0.01, r), 2500) * env(0.01, 0.0003, 0.004), t0, r.uniform(0.15, 0.6))
    return buf


@familia
def hielo(r):
    D = 1.0
    buf = silencio(D)
    poner(buf, clic(r, 0.01, 3000) * 0.5, 0.0)
    for k in range(7):
        poner(buf, ping(float(r.choice([5200, 6400, 7400, 8800])), 0.35, 0.09) * r.uniform(0.3, 0.7), 0.01 + k * 0.06 + r.uniform(0, 0.03), 0.5)
    return buf


@familia
def sol(r):
    D = 1.7
    buf = silencio(D)
    for f in (262, 330, 392, 523):
        s = np.sin(2 * np.pi * f * tt(D)) * env_cos(D, 0.4, 0.9)
        poner(buf, s, 0.0, 0.35)
    for k in range(6):
        poner(buf, ping(float(r.choice([2093, 2637, 3136])), 0.5, 0.15) * 0.2, 0.3 + k * 0.12)
    return buf


@familia
def luna(r):
    D = 1.8
    buf = silencio(D)
    for k, f in enumerate((880, 659, 523)):
        poner(buf, chime(float(f), 1.2, 0.5), k * 0.28, 0.6)
    return eco(buf, ((0.18, 0.25), (0.35, 0.15)))[:_n(D)]


@familia
def idea(r):
    D = 0.9
    buf = silencio(D)
    y = np.sin(2 * np.pi * np.cumsum(glide_exp(900, 2637, 0.05)) / SR) * env(0.05, 0.001, 0.04)
    poner(buf, y, 0.0, 0.5)
    poner(buf, chime(2637, 0.8, 0.28), 0.04, 0.8)
    for k in range(4):
        poner(buf, ping(float(r.choice([3951, 4699, 5274])), 0.3, 0.07) * 0.2, 0.15 + k * 0.05)
    return buf


@familia
def telefono(r):
    D = 1.6
    buf = silencio(D)
    for base in (0.0, 0.8):
        t = tt(0.4)
        tono = (np.sin(2 * np.pi * 440 * t) + np.sin(2 * np.pi * 480 * t)) * (0.6 + 0.4 * np.sign(np.sin(2 * np.pi * 20 * t)))
        poner(buf, tono * env_cos(0.4, 0.01, 0.02), base, 0.35)
    return buf


@familia
def notificacion(r):
    D = 0.7
    buf = silencio(D)
    poner(buf, chime(1568, 0.4, 0.14), 0.0, 0.7)
    poner(buf, chime(2349, 0.55, 0.2), 0.11, 0.8)
    return buf


@familia
def mensaje(r):
    D = 0.4
    buf = silencio(D)
    for k, (a, b) in enumerate(((500, 1100), (650, 1500))):
        y = np.sin(2 * np.pi * np.cumsum(glide_exp(a, b, 0.07)) / SR) * env(0.07, 0.001, 0.03)
        poner(buf, y, k * 0.1, 0.8)
    return buf


@familia
def alarma(r):
    D = 1.4
    buf = silencio(D)
    for k in range(14):
        t = tt(0.045)
        s = (np.sin(2 * np.pi * 1700 * t) + 0.5 * np.sin(2 * np.pi * 2300 * t)) * env_cos(0.045, 0.003, 0.01)
        poner(buf, s, k * 0.06 if k < 7 else 0.65 + (k - 7) * 0.06, 0.5)
    return buf


@familia
def tictac(r):
    D = 1.1
    buf = silencio(D)
    for k in range(4):
        f = 1500 if k % 2 == 0 else 1050
        poner(buf, mix(clic(r, 0.01, 1500) * 0.8, np.sin(2 * np.pi * f * tt(0.03)) * env(0.03, 0.0005, 0.008) * 0.6), k * 0.26)
    return buf


@familia
def llave(r):
    D = 0.9
    buf = silencio(D)
    for k in range(9):
        poner(buf, ping(float(r.uniform(2800, 6000)), 0.25, 0.05) * r.uniform(0.3, 0.8), k * 0.045 + r.uniform(0, 0.02), 0.6)
        poner(buf, clic(r, 0.004, 3000) * 0.3, k * 0.045)
    return buf


@familia
def candado(r):
    D = 0.4
    buf = silencio(D)
    for t0, f in ((0.0, 900), (0.13, 640)):
        poner(buf, mix(clic(r, 0.006, 2000) * 0.9, np.sin(2 * np.pi * f * tt(0.05)) * env(0.05, 0.0004, 0.01) * 0.6), t0)
    poner(buf, thump(200, 110, 0.08, 0.02) * 0.4, 0.13)
    return buf


@familia
def martillo(r):
    D = 0.6
    buf = silencio(D)
    poner(buf, clic(r, 0.01, 800) * 0.9, 0.0)
    poner(buf, thump(160, 70, 0.15, 0.04) * 0.8, 0.0)
    t = tt(0.5)
    poner(buf, (np.sin(2 * np.pi * 1850 * t) + 0.6 * np.sin(2 * np.pi * 2930 * t) + 0.4 * np.sin(2 * np.pi * 4410 * t)) * np.exp(-t / 0.11) * 0.35, 0.0)
    return buf


@familia
def golpe(r):
    D = 0.5
    buf = silencio(D)
    poner(buf, thump(150, 48, 0.3, 0.08) * 1.0, 0.0)
    poner(buf, bajos(ruido(0.08, r), 3000) * env(0.08, 0.0006, 0.02) * 0.7, 0.0)
    poner(buf, clic(r, 0.01, 1200) * 0.5, 0.0)
    return buf


@familia
def patada(r):
    D = 0.35
    buf = silencio(D)
    poner(buf, thump(130, 65, 0.2, 0.05) * 1.0, 0.0)
    poner(buf, bajos(ruido(0.05, r), 1800) * env(0.05, 0.0006, 0.012) * 0.6, 0.0)
    return buf


@familia
def rebote(r):
    D = 1.5
    buf = silencio(D)
    for t0, g in ((0.0, 1.0), (0.38, 0.75), (0.68, 0.55), (0.91, 0.4), (1.08, 0.28), (1.19, 0.2)):
        s = np.sin(2 * np.pi * np.cumsum(glide_exp(190, 95, 0.09)) / SR) * env(0.09, 0.001, 0.03)
        poner(buf, mix(s, bajos(ruido(0.02, r), 900) * env(0.02, 0.0005, 0.006) * 0.4), t0, g)
    return buf


@familia
def diana(r):
    D = 0.45
    buf = silencio(D)
    poner(buf, thump(180, 80, 0.12, 0.03) * 0.9, 0.0)
    poner(buf, clic(r, 0.006, 2500) * 0.6, 0.0)
    poner(buf, ping(1900, 0.3, 0.07) * 0.3, 0.005)
    return buf


@familia
def meta(r):
    D = 1.5
    buf = silencio(D)
    for t0, d in ((0.0, 0.16), (0.3, 0.16), (0.6, 0.8)):
        poner(buf, bajos(osc(880, d, 'sq'), 2600) * env_cos(d, 0.005, 0.03), t0, 0.5)
    return buf


@familia
def silbato(r):
    D = 0.7
    t = tt(D)
    f = 2900 + 150 * np.sin(2 * np.pi * 3 * t)
    trino = 0.7 + 0.3 * np.sign(np.sin(2 * np.pi * 38 * t))
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * trino
    y += altos(ruido(D, r), 3000) * 0.05
    return y * env_cos(D, 0.02, 0.08)


@familia
def tambor(r):
    D = 1.5
    buf = silencio(D)
    t0 = 0.0
    k = 0
    while t0 < 0.95:
        g = 0.3 + 0.6 * (t0 / 0.95)
        poner(buf, mix(bajos(ruido(0.07, r), 5000) * env(0.07, 0.0006, 0.02) * 0.8, np.sin(2 * np.pi * 190 * tt(0.07)) * env(0.07, 0.0006, 0.025) * 0.5), t0, g)
        t0 += 0.075 - 0.035 * (t0 / 0.95)
        k += 1
    poner(buf, thump(130, 60, 0.4, 0.12) * 1.0, 1.0)
    poner(buf, altos(ruido(0.5, r), 4000) * env(0.5, 0.001, 0.16) * 0.5, 1.0)
    return buf


@familia
def guitarra(r):
    D = 1.6
    buf = silencio(D)
    for k, f in enumerate((82.4, 123.5, 164.8, 207.7, 247.0, 329.6)):
        poner(buf, ks(f, 1.4, 0.9965, r) * env(1.4, 0.001, 0.7), k * 0.018, 0.4)
    return bajos(buf, 5000)


@familia
def piano(r):
    D = 1.4
    buf = silencio(D)
    for k, f in enumerate((523.25, 659.25, 783.99, 1046.5)):
        t = tt(1.0)
        s = sum((1.0 / h ** 1.3) * np.sin(2 * np.pi * f * h * t) * np.exp(-t / (0.5 / (1 + 0.35 * h))) for h in range(1, 7))
        poner(buf, s * np.minimum(t / 0.002, 1), k * 0.11, 0.5)
    return buf


@familia
def micro(r):
    D = 0.6
    buf = silencio(D)
    for k in range(3):
        poner(buf, mix(thump(220, 90, 0.12, 0.03) * 0.8, clic(r, 0.01, 200) * 0.4), k * 0.1)
    poner(buf, np.sin(2 * np.pi * 2400 * tt(0.3)) * env_cos(0.3, 0.05, 0.25) * 0.08, 0.28)
    return buf


@familia
def sirena(r):
    D = 1.7
    n = _n(D)
    t = np.linspace(0, 1, n)
    f = 750 + 450 * np.sin(2 * np.pi * 1.4 * t - np.pi / 2)
    y = bajos(osc(f, D, 'sq'), 3500) * 0.7 + osc(f, D, 'sin') * 0.5
    return y * env_cos(D, 0.05, 0.25)


@familia
def claxon(r):
    D = 0.7
    y = bajos(osc(415, D, 'sq') + osc(520, D, 'sq'), 2500)
    return y * env_cos(D, 0.01, 0.06)


@familia
def tren(r):
    D = 1.6
    y = sum(osc(f, D, 'saw') for f in (311, 370, 466, 587))
    y = bajos(y, 1800) * env_cos(D, 0.12, 0.35)
    y += banda(ruido(D, r), 300, 2000) * 0.08 * env_cos(D, 0.12, 0.35)
    return y


@familia
def motor(r):
    D = 1.6
    f = glide_exp(38, 130, 1.0)
    f = np.concatenate([f, np.full(_n(D) - len(f), 130.0)])
    y = osc(f, D, 'saw') * 0.6 + osc(f * 2, D, 'sq') * 0.2
    y = bajos(y, 900) * (0.85 + 0.15 * np.sign(np.sin(2 * np.pi * np.cumsum(f / 2) / SR)))
    y += banda(ruido(D, r), 200, 1500) * 0.25
    return y * env_cos(D, 0.04, 0.4)


@familia
def avion(r):
    D = 2.0
    n = _n(D)
    ru = ruido(D, r)
    y = np.zeros(n)
    pasos = 12
    for k in range(pasos):
        a, b = k * n // pasos, (k + 1) * n // pasos
        c = 500 + 1900 * math.sin(math.pi * k / (pasos - 1)) ** 1.3
        y[a:b] = banda(ru[a:b + 600] if b + 600 <= n else ru[a:], c * 0.55, c * 1.5)[:b - a]
    y += bajos(ruido(D, r), 250) * 0.6 * env_cos(D, 0.8, 0.8)
    return y * env_cos(D, 0.8, 0.9) * 1.3


# ---- caras y criaturas (voz sintetizada con formantes) -------------------------------------
def _fuente_voz(f0, d, aspereza=0.0, r=None):
    s = osc(f0, d, 'saw')
    s = bajos(s, 5000)
    if aspereza and r is not None:
        s += ruido(d, r) * aspereza
    return s


@familia
def risa(r):
    D = 1.0
    buf = silencio(D)
    for k in range(4):
        d = 0.15
        f0 = 250 - k * 12 + r.uniform(-4, 4)
        src = _fuente_voz(vib(f0, d, 9, 0.04), d, 0.0, r)
        a = formantes(src, lambda t: [(800, 140, 1.0), (1250, 190, 0.7), (2500, 300, 0.35)])
        h = banda(ruido(0.04, r), 1500, 5000) * env(0.04, 0.001, 0.02) * 0.25
        poner(buf, a * env_cos(d, 0.015, 0.07), 0.05 + k * 0.2, 0.9)
        poner(buf, h, 0.02 + k * 0.2)
    return buf


@familia
def triste(r):
    D = 2.0
    buf = silencio(D)
    notas = [(233, 0.34), (220, 0.34), (208, 0.34), (196, 0.9)]
    t0 = 0.0
    for k, (f, d) in enumerate(notas):
        fr = vib(f, d, 5.5, 0.012 if k < 3 else 0.03, 0.15) if k == 3 else f
        s = osc(fr * np.ones(_n(d)) if np.isscalar(fr) else fr, d, 'saw')
        wah = lambda t, kk=k: [(500 + 450 * (0.5 + 0.5 * math.sin(math.pi * min(t / 0.34, 1.0))) if kk < 3 else 800 - 250 * min(t / 0.9, 1.0), 220, 1.0), (1300, 280, 0.5)]
        poner(buf, formantes(s, wah) * env_cos(d, 0.03, 0.06), t0, 0.8)
        t0 += d + 0.015
    return buf


@familia
def susto(r):
    D = 1.1
    buf = silencio(D)
    inhal = banda(ruido(0.3, r), 500, 3500) * env_cos(0.3, 0.2, 0.05) * 0.5
    poner(buf, inhal, 0.0)
    for f in (880, 932, 1175, 1319):
        poner(buf, bajos(osc(f, 0.9, 'saw'), 5000) * env(0.9, 0.004, 0.35), 0.3, 0.2)
    poner(buf, thump(140, 60, 0.3, 0.08) * 0.5, 0.3)
    return buf


@familia
def enojo(r):
    D = 1.0
    n = _n(D)
    t = tt(D)
    f0 = 72 + 12 * np.sin(2 * np.pi * 5 * t)
    s = osc(f0, D, 'saw') * (0.7 + 0.3 * np.sign(np.sin(2 * np.pi * 28 * t)))
    s = formantes(s + ruido(D, r) * 0.15, lambda t: [(500, 160, 1.0), (1000, 220, 0.8), (2200, 300, 0.4)])
    return np.tanh(s * 2.0) * env_cos(D, 0.08, 0.3)


@familia
def pensando(r):
    D = 1.2
    t = tt(D)
    f0 = 170 + 35 * np.sin(np.pi * t / D) ** 1.2
    s = _fuente_voz(vib(f0, D, 5, 0.01), D)
    y = formantes(s, lambda tm: [(270, 80, 1.0), (1000, 150, 0.35), (2200, 250, 0.2)])
    return y * env_cos(D, 0.12, 0.3)


@familia
def dormir(r):
    D = 2.0
    y = np.zeros(_n(D))
    for k, base in enumerate((0.1, 1.05)):
        d = 0.85
        t = tt(d)
        inh = banda(ruido(d, r), 120, 900) * np.sin(np.pi * t / d) ** 1.5
        rasp = osc(55 + 6 * np.sin(2 * np.pi * 7 * t), d, 'saw') * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 26 * t))) * np.sin(np.pi * t / d) ** 2
        poner(y, (inh * 1.2 + bajos(rasp, 300) * 0.8) * 0.9, base)
    return y


@familia
def fantasma(r):
    D = 1.6
    t = tt(D)
    f = 520 + 160 * np.sin(2 * np.pi * 0.6 * t) - 120 * t / D
    y = np.sin(2 * np.pi * np.cumsum(vib(f, D, 5.2, 0.05, 0.2)) / SR)
    y = formantes(y + 0.3 * osc(f, D, 'tri'), lambda tm: [(400, 100, 1.0), (850, 160, 0.5)])
    return eco(y * env_cos(D, 0.4, 0.7), ((0.12, 0.3), (0.26, 0.2)))[:_n(D)]


@familia
def calavera(r):
    D = 1.4
    buf = silencio(D)
    poner(buf, thump(85, 38, 0.8, 0.25) * 1.1, 0.0)
    ch = banda(ruido(0.6, r), 700, 2200) * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 30 * tt(0.6)))) * env_cos(0.6, 0.05, 0.3)
    poner(buf, ch, 0.15, 0.25)
    poner(buf, bajos(osc(glide_exp(220, 90, 0.9), 0.9, 'saw'), 700) * env(0.9, 0.005, 0.4), 0.0, 0.45)
    return buf


@familia
def alien(r):
    D = 1.2
    t = tt(D)
    f = 900 + 500 * np.sin(2 * np.pi * 3.0 * t) + 700 * np.sin(2 * np.pi * 0.9 * t)
    y = np.sin(2 * np.pi * np.cumsum(f + 200 * np.sin(2 * np.pi * 40 * t)) / SR)
    buf = silencio(D)
    poner(buf, y * env_cos(D, 0.05, 0.3), 0.0, 0.7)
    for k in range(5):
        poner(buf, ping(float(r.uniform(1500, 3500)), 0.2, 0.05) * 0.25, 0.3 + k * 0.14)
    return buf


@familia
def robot(r):
    D = 1.0
    buf = silencio(D)
    t0 = 0.0
    while t0 < 0.8:
        d = float(r.choice([0.04, 0.06, 0.09]))
        f = float(r.choice([440, 660, 880, 1320, 1760, 2200]))
        s = np.sin(2 * np.pi * f * tt(d)) * np.sign(np.sin(2 * np.pi * 70 * tt(d)) + 0.2)
        poner(buf, s * env_cos(d, 0.004, 0.008), t0, 0.5)
        t0 += d + float(r.choice([0.01, 0.03]))
    return buf


@familia
def pajaro(r):
    D = 0.9
    buf = silencio(D)
    for t0, (a, b) in zip((0.02, 0.18, 0.34, 0.62), ((3200, 5200), (3600, 5600), (3000, 5000), (3400, 6000))):
        d = 0.1
        f = glide(a, b, d) * (1 + 0.04 * np.sin(2 * np.pi * 42 * tt(d)))
        poner(buf, np.sin(2 * np.pi * np.cumsum(f) / SR) * env_cos(d, 0.01, 0.04), t0, 0.7)
    return buf


@familia
def gato(r):
    D = 1.0
    d = 0.8
    t = tt(d)
    f0 = 520 - 140 * (t / d) + 50 * np.sin(np.pi * t / d)
    src = _fuente_voz(vib(f0, d, 6, 0.015), d)
    y = formantes(src, lambda tm: [(700 + 600 * math.sin(math.pi * tm / 0.8) ** 1.0, 120, 1.0), (1500 + 900 * math.sin(math.pi * tm / 0.8), 200, 0.8), (3200, 400, 0.3)])
    buf = silencio(D)
    poner(buf, y * env_cos(d, 0.12, 0.25), 0.03)
    return buf


@familia
def perro(r):
    D = 0.8
    buf = silencio(D)
    for t0 in (0.02, 0.3):
        d = 0.16
        f0 = glide_exp(340, 200, d)
        src = _fuente_voz(f0, d, 0.25, r)
        y = formantes(src, lambda tm: [(650 - 100 * tm / 0.16, 150, 1.0), (1100, 220, 0.8), (2400, 350, 0.3)])
        poner(buf, y * env(d, 0.004, 0.07), t0, 1.0)
        poner(buf, clic(r, 0.01, 800) * 0.3, t0)
    return buf


@familia
def rana(r):
    D = 0.9
    buf = silencio(D)
    for t0 in (0.05, 0.4):
        d = 0.28
        t = tt(d)
        s = osc(glide(150, 210, d), d, 'saw') * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 34 * t)))
        y = formantes(s, lambda tm: [(350 + 500 * tm / 0.28, 120, 1.0), (1500, 250, 0.5)])
        poner(buf, y * env_cos(d, 0.02, 0.1), t0, 0.9)
    return buf


@familia
def vaca(r):
    D = 1.6
    t = tt(D)
    f0 = 130 - 28 * (t / D) + 6 * np.sin(2 * np.pi * 4 * t)
    src = _fuente_voz(f0, D)
    y = formantes(src, lambda tm: [(350 + 180 * min(tm / 0.5, 1.0), 110, 1.0), (800 - 150 * min(tm / 1.2, 1.0), 180, 0.7), (2300, 300, 0.15)])
    return y * env_cos(D, 0.25, 0.4)


@familia
def cerdo(r):
    D = 0.9
    buf = silencio(D)
    for t0, g in ((0.02, 1.0), (0.4, 0.8)):
        d = 0.3
        f0 = glide(210, 130, d) * (1 + 0.1 * np.sin(2 * np.pi * 22 * tt(d)))
        src = _fuente_voz(f0, d, 0.15, r)
        y = formantes(src, lambda tm: [(400 + 200 * math.sin(math.pi * tm / 0.3), 140, 1.0), (1000, 200, 0.6), (2200, 300, 0.25)])
        poner(buf, y * env_cos(d, 0.03, 0.1), t0, g)
    return buf


@familia
def pato(r):
    D = 0.9
    buf = silencio(D)
    for t0 in (0.02, 0.34):
        d = 0.22
        t = tt(d)
        s = osc(glide(430, 330, d), d, 'saw') * (0.6 + 0.4 * np.sign(np.sin(2 * np.pi * 75 * t)))
        y = formantes(s, lambda tm: [(900, 130, 1.0), (1700, 200, 0.8), (2800, 300, 0.3)])
        poner(buf, y * env_cos(d, 0.01, 0.07), t0, 0.9)
    return buf


@familia
def leon(r):
    D = 1.8
    t = tt(D)
    f0 = 85 + 15 * np.sin(2 * np.pi * 8 * t) - 25 * t / D
    s = osc(f0, D, 'saw') * (0.6 + 0.4 * np.sign(np.sin(2 * np.pi * 32 * t)))
    s += ruido(D, r) * 0.3
    y = formantes(s, lambda tm: [(450 + 250 * math.sin(math.pi * tm / 1.8), 180, 1.0), (1200, 300, 0.6), (2400, 400, 0.3)])
    return np.tanh(y * 1.5) * env_cos(D, 0.2, 0.6)


@familia
def abeja(r):
    D = 1.2
    t = tt(D)
    f = 215 + 20 * np.sin(2 * np.pi * 3 * t)
    s = osc(f, D, 'saw') * (0.6 + 0.4 * np.sin(2 * np.pi * 150 * t))
    y = banda(s, 200, 1800) + banda(ruido(D, r), 700, 3000) * 0.1
    return y * env_cos(D, 0.15, 0.4)


@familia
def serpiente(r):
    D = 1.4
    y = altos(ruido(D, r), 3500) * env_cos(D, 0.35, 0.5)
    t = tt(D)
    y += banda(ruido(D, r), 800, 3000) * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 45 * t))) * env_cos(D, 0.5, 0.5) * 0.25
    return y


@familia
def buho(r):
    D = 1.2
    buf = silencio(D)
    for t0, d in ((0.02, 0.4), (0.5, 0.6)):
        t = tt(d)
        f = glide(400, 360, d)
        y = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.3 * np.sin(2 * np.pi * np.cumsum(f) * 2 / SR)
        poner(buf, y * env_cos(d, 0.08, 0.18), t0, 0.7)
    return buf


# ---- comida, bebida, varios ---------------------------------------------------------------
@familia
def crunch(r):
    D = 0.9
    buf = silencio(D)
    for t0 in (0.0, 0.26, 0.5):
        for _ in range(9):
            tt0 = t0 + r.uniform(0, 0.09)
            poner(buf, banda(ruido(0.012, r), r.uniform(800, 2000), r.uniform(3000, 7000)) * env(0.012, 0.0004, 0.004), tt0, r.uniform(0.3, 1.0))
        poner(buf, thump(200, 110, 0.06, 0.02) * 0.4, t0)
    return buf


@familia
def clink(r):
    D = 1.0
    buf = silencio(D)
    for t0, f, g in ((0.0, 2400, 1.0), (0.01, 3150, 0.6)):
        t = tt(0.9)
        poner(buf, (np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * f * 1.51 * t)) * np.exp(-t / 0.28) * np.minimum(t / 0.001, 1), t0, g * 0.6)
    poner(buf, clic(r, 0.005, 3000) * 0.5, 0.0)
    return buf


@familia
def champan(r):
    D = 1.8
    buf = silencio(D)
    poner(buf, bajos(ruido(0.06, r), 3000) * env(0.06, 0.0005, 0.016), 0.0, 1.0)
    poner(buf, thump(180, 70, 0.2, 0.05) * 0.9, 0.0)
    poner(buf, altos(ruido(1.5, r), 3500) * env(1.5, 0.02, 0.5) * 0.22, 0.02)
    for _ in range(40):
        poner(buf, np.sin(2 * np.pi * float(r.uniform(2500, 6500)) * tt(0.01)) * env(0.01, 0.0003, 0.003), 0.1 + abs(r.normal(0.0, 0.5)), r.uniform(0.1, 0.35))
    return buf


@familia
def sorbo(r):
    D = 0.8
    n = _n(D)
    ru = ruido(D, r)
    y = np.zeros(n)
    pasos = 8
    for k in range(pasos):
        a, b = k * n // pasos, (k + 1) * n // pasos
        c = 1200 + 1800 * k / (pasos - 1)
        y[a:b] = banda(ru[a:b + 300] if b + 300 <= n else ru[a:], c * 0.8, c * 1.2)[:b - a]
    return y * env_cos(D, 0.15, 0.3) * 1.5 * (0.6 + 0.4 * np.sin(2 * np.pi * 14 * tt(D)))


@familia
def regalo(r):
    D = 1.3
    buf = silencio(D)
    for k in range(14):
        poner(buf, banda(ruido(0.03, r), 1500, 6000) * env(0.03, 0.001, 0.01), k * 0.035 + r.uniform(0, 0.02), r.uniform(0.2, 0.6))
    for k, f in enumerate((1568, 1976, 2637, 3136)):
        poner(buf, chime(float(f), 0.6, 0.18) * 0.5, 0.55 + k * 0.08)
    return buf


@familia
def libro(r):
    D = 0.6
    n = _n(0.3)
    ru = ruido(0.3, r)
    y = np.zeros(n)
    pasos = 6
    for k in range(pasos):
        a, b = k * n // pasos, (k + 1) * n // pasos
        c = 2000 + 3500 * math.sin(math.pi * k / (pasos - 1))
        y[a:b] = banda(ru[a:b + 200] if b + 200 <= n else ru[a:], c * 0.6, c * 1.5)[:b - a]
    buf = silencio(D)
    poner(buf, y * env_cos(0.3, 0.05, 0.15), 0.0, 1.2)
    poner(buf, thump(150, 90, 0.08, 0.02) * 0.3, 0.27)
    return buf


@familia
def claqueta(r):
    D = 0.4
    buf = silencio(D)
    poner(buf, clic(r, 0.01, 700) * 1.0, 0.0)
    t = tt(0.1)
    poner(buf, (np.sin(2 * np.pi * 900 * t) + 0.7 * np.sin(2 * np.pi * 1850 * t)) * np.exp(-t / 0.018), 0.0, 0.7)
    poner(buf, thump(200, 100, 0.06, 0.015) * 0.5, 0.0)
    return buf


@familia
def pulgar_arriba(r):
    D = 0.7
    buf = silencio(D)
    poner(buf, burbuja(r)[:_n(0.1)], 0.0, 0.8)
    poner(buf, chime(1047, 0.4, 0.15), 0.07, 0.7)
    poner(buf, chime(1568, 0.5, 0.2), 0.16, 0.8)
    return buf


@familia
def pulgar_abajo(r):
    D = 0.8
    buf = silencio(D)
    for k, f in enumerate((247, 185)):
        poner(buf, bajos(osc(f, 0.3, 'saw'), 800) * env_cos(0.3, 0.01, 0.1), k * 0.2, 0.7)
    return buf


@familia
def ok(r):
    return chime(1760, 0.7, 0.25) * 0.8


@familia
def rezo(r):
    D = 2.0
    t = tt(D)
    y = (np.sin(2 * np.pi * 440 * t) + 0.5 * np.sin(2 * np.pi * 1190 * t) * np.exp(-t / 0.7) + 0.25 * np.sin(2 * np.pi * 2300 * t) * np.exp(-t / 0.35)) * np.exp(-t / 0.9)
    y *= (1 + 0.15 * np.sin(2 * np.pi * 5 * t))
    return y * np.minimum(t / 0.01, 1)


@familia
def musculo(r):
    D = 1.0
    buf = silencio(D)
    s = bajos(osc(glide_exp(180, 900, 0.5), 0.5, 'saw'), 3000) * env_cos(0.5, 0.05, 0.05)
    poner(buf, s, 0.0, 0.5)
    poner(buf, thump(150, 55, 0.4, 0.12) * 1.0, 0.5)
    poner(buf, clic(r, 0.02, 600) * 0.6, 0.5)
    return buf


@familia
def saludo(r):
    D = 0.6
    n = _n(0.4)
    ru = ruido(0.4, r)
    y = np.zeros(n)
    pasos = 7
    for k in range(pasos):
        a, b = k * n // pasos, (k + 1) * n // pasos
        c = 700 + 1400 * math.sin(math.pi * k / (pasos - 1))
        y[a:b] = banda(ru[a:b + 200] if b + 200 <= n else ru[a:], c * 0.6, c * 1.5)[:b - a]
    buf = silencio(D)
    poner(buf, y * env_cos(0.4, 0.12, 0.2), 0.0, 0.9)
    return buf


@familia
def mente_explota(r):
    D = 2.1
    buf = silencio(D)
    poner(buf, cohete(r)[:_n(0.8)] * np.linspace(0.3, 1.0, _n(0.8)), 0.0, 0.7)
    poner(buf, explosion(r)[:_n(1.3)], 0.8, 0.9)
    return buf


@familia
def ojos(r):
    D = 1.1
    buf = silencio(D)
    for k, f in enumerate((110, 98)):
        s = bajos(osc(f, 0.35, 'saw') + osc(f * 1.005, 0.35, 'saw'), 700) * env(0.35, 0.005, 0.18)
        poner(buf, s, k * 0.3, 0.8)
        poner(buf, thump(f * 1.3, f * 0.6, 0.2, 0.05) * 0.4, k * 0.3)
    return eco(buf, ((0.12, 0.3),))[:_n(D)]


@familia
def censura(r):
    D = 0.6
    y = np.sin(2 * np.pi * 1000 * tt(D)) * env_cos(D, 0.01, 0.02)
    return y * 0.7


@familia
def boing(r):
    D = 0.8
    t = tt(D)
    f = 220 + 520 * np.sin(np.pi * np.minimum(t / 0.5, 1.0)) ** 1.2
    f = f * (1 + 0.12 * np.sin(2 * np.pi * 14 * t) * np.exp(-t / 0.3))
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.3 * np.sin(2 * np.pi * np.cumsum(f * 2) / SR)
    return y * env(D, 0.005, 0.22)


# ---- genéricos: variedad para los grupos sin sonido propio -----------------------------------------------
@familia
def pop_a(r):
    D = 0.25
    buf = silencio(D)
    y = np.sin(2 * np.pi * np.cumsum(glide_exp(500, 1500, 0.06)) / SR) * env(0.06, 0.001, 0.025)
    poner(buf, y, 0.0, 0.9)
    poner(buf, ping(1900, 0.2, 0.05) * 0.2, 0.05)
    return buf


@familia
def pop_b(r):
    D = 0.3
    t = tt(D)
    y = (np.sin(2 * np.pi * 740 * t) + 0.5 * np.sin(2 * np.pi * 1480 * t) * np.exp(-t / 0.04)) * env(D, 0.001, 0.07)
    return y


@familia
def pop_c(r):
    D = 0.35
    t = tt(D)
    return (np.sin(2 * np.pi * 988 * t) + 0.6 * np.sin(2 * np.pi * 988 * 3.93 * t) * np.exp(-t / 0.03)) * env(D, 0.001, 0.1)


@familia
def pop_d(r):
    D = 0.3
    buf = silencio(D)
    for k, f in enumerate((660, 990)):
        poner(buf, np.sin(2 * np.pi * f * tt(0.1)) * env(0.1, 0.001, 0.04), k * 0.07, 0.8)
    return buf


@familia
def ding(r):
    return chime(1568, 0.7, 0.22) * 0.8


@familia
def tick(r):
    D = 0.12
    buf = silencio(D)
    poner(buf, mix(clic(r, 0.008, 1200) * 0.9, np.sin(2 * np.pi * 1400 * tt(0.03)) * env(0.03, 0.0004, 0.007) * 0.5), 0.0)
    return buf


@familia
def swish(r):
    D = 0.45
    n = _n(0.35)
    ru = ruido(0.35, r)
    y = np.zeros(n)
    pasos = 7
    for k in range(pasos):
        a, b = k * n // pasos, (k + 1) * n // pasos
        c = 500 * (6 ** (k / (pasos - 1)))
        y[a:b] = banda(ru[a:b + 200] if b + 200 <= n else ru[a:], c * 0.6, c * 1.5)[:b - a]
    buf = silencio(D)
    poner(buf, y * env_cos(0.35, 0.18, 0.12), 0.0, 1.1)
    return buf


# ------------------------------------------------------------------------------------------------ salida
def _semilla(nombre):
    return zlib.crc32(nombre.encode('utf-8')) & 0xFFFFFFFF


def fabricar(nombre):
    r = np.random.default_rng(_semilla(nombre))
    x = np.asarray(F[nombre](r), dtype=float)
    x = np.nan_to_num(x)
    x = fundido(x, 0.0015, 0.03)
    return normal(x, 0.8)


def guardar(nombre, x, carpeta):
    os.makedirs(carpeta, exist_ok=True)
    ruta = os.path.join(carpeta, nombre + '.wav')
    with wave.open(ruta, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype('<i2').tobytes())
    return ruta


def hoja_de_espectrogramas(nombres, salida, columnas=8):
    from PIL import Image, ImageDraw
    celda_w, celda_h = 220, 110
    filas = (len(nombres) + columnas - 1) // columnas
    img = Image.new('RGB', (columnas * celda_w, filas * celda_h), (12, 14, 20))
    dib = ImageDraw.Draw(img)
    for i, nom in enumerate(nombres):
        x = fabricar(nom)
        ven, hop = 512, 256
        w = np.hanning(ven)
        cols = []
        for a in range(0, max(1, len(x) - ven), hop):
            esp = np.abs(np.fft.rfft(x[a:a + ven] * w))[:128]
            cols.append(esp)
        M = np.array(cols).T[::-1]
        M = 20 * np.log10(M + 1e-6)
        M = np.clip((M - (M.max() - 70)) / 70, 0, 1)
        ancho = celda_w - 8
        alto = celda_h - 22
        tira = Image.fromarray((np.stack([M * 255, M ** 1.5 * 255, (1 - M) * 120 * M * 2 + M * 60], axis=-1)).astype('uint8')).resize((ancho, alto))
        px, py = (i % columnas) * celda_w + 4, (i // columnas) * celda_h + 18
        img.paste(tira, (px, py))
        dib.text((px, py - 14), f'{nom} {len(x) / SR:.1f}s', fill=(220, 220, 230))
    img.save(salida)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--salida', default=DEFECTO_SALIDA)
    ap.add_argument('--solo', nargs='*')
    ap.add_argument('--hoja')
    ap.add_argument('--solo-sintesis', action='store_true', help='ignora reales/ y sintetiza todo')
    a = ap.parse_args()
    nombres = a.solo or sorted(F)
    total = 0
    reales_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'reales')
    n_reales = 0
    for n in nombres:
        real = os.path.join(reales_dir, n + '.wav')
        if os.path.isfile(real) and not a.solo_sintesis:
            os.makedirs(a.salida, exist_ok=True)
            ruta = os.path.join(a.salida, n + '.wav')
            shutil.copyfile(real, ruta)          # una grabación CC0 de reales/ manda sobre la síntesis
            n_reales += 1
        else:
            ruta = guardar(n, fabricar(n), a.salida)
        total += os.path.getsize(ruta)
    fj = os.path.join(reales_dir, 'FUENTES.json')
    if os.path.isfile(fj) and not a.solo_sintesis:
        fu = json.load(open(fj, encoding='utf-8'))
        lineas = ['SONIDOS DE LOS EMOJIS · origen y licencia', '',
                  'Las grabaciones de abajo son CC0 (dominio público): se pueden usar y redistribuir sin atribución. Se citan por cortesía.',
                  'Todos los demás sonidos de esta carpeta los sintetiza CineCaptions con código propio (sin derechos de terceros).', '']
        for fam, inf in sorted(fu.items()):
            lineas.append(f"{fam}.wav  <-  {inf['archivo']}  ·  {inf['pack']}  ·  {inf['autor']}  ·  {inf['licencia']}  ·  {inf['url']}")
        with open(os.path.join(a.salida, 'LICENCIAS.txt'), 'w', encoding='utf-8') as fh:
            fh.write(chr(10).join(lineas) + chr(10))
    print(f'{len(nombres)} sonidos en {os.path.abspath(a.salida)} ({total / 1024:.0f} KB): {n_reales} grabaciones reales CC0 + {len(nombres) - n_reales} sintetizados')
    if a.hoja:
        hoja_de_espectrogramas(nombres, a.hoja)
        print('hoja:', a.hoja)


if __name__ == '__main__':
    main()
