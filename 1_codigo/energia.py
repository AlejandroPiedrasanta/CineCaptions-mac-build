# CineCaptions · By Cinema Productions
# 1_codigo/energia.py — la «curva de energía» del habla: cuánta intensidad tiene cada tramo del video, calculada desde las palabras.
"""
La energía de cada palabra sale de la RAPIDEZ con que se habla alrededor de ella (palabras por segundo en una ventana de ±3 s,
con las pausas contando como calma). Se normaliza contra el propio video (percentiles 10-90): lo «rápido» es relativo a quien
habla. Con ella los efectos de sonido acompañan el ritmo: en los tramos intensos suena (casi) cada palabra y en los calmados
solo las importantes; así el video «respira» en vez de sonar igual de principio a fin.

    energia_de_palabras(palabras)   [0..1] por palabra          (palabras: [{'start', 'end'}] o [{'t', 'fin'}])
    deja_pasar(energia, i, ...)     True si esa palabra debe sonar (determinista: mismo video = mismo resultado)
"""
import numpy as np

VENTANA_S = 3.0
PISO = 0.30            # probabilidad minima de sonar en lo mas calmado


def _tiempos(palabras):
    ini, fin = [], []
    for p in palabras:
        a = float(p.get('start', p.get('t')) or 0.0)
        b = float(p.get('end', p.get('fin')) or a)
        ini.append(a)
        fin.append(max(a, b))
    return np.array(ini), np.array(fin)


def energia_de_palabras(palabras, ventana=VENTANA_S):
    """Una energia 0..1 por palabra: palabras habladas por segundo alrededor (las pausas la bajan)."""
    if not palabras:
        return []
    ini, fin = _tiempos(palabras)
    n = len(ini)
    tasa = np.zeros(n)
    for i in range(n):
        a, b = ini[i] - ventana, ini[i] + ventana
        cuenta = np.count_nonzero((ini >= a) & (ini <= b))
        tasa[i] = cuenta / (2.0 * ventana)
    if n < 4:
        return [1.0] * n
    lo, hi = np.percentile(tasa, 10), np.percentile(tasa, 90)
    if hi - lo < 1e-6:
        return [0.6] * n
    return [float(x) for x in np.clip((tasa - lo) / (hi - lo), 0.0, 1.0)]


def deja_pasar(energia, i, semilla=7, importante=False, piso=PISO):
    """True si la palabra i suena: siempre las importantes; el resto con probabilidad piso..1 segun la energia (determinista)."""
    if importante or not energia:
        return True
    e = energia[min(i, len(energia) - 1)]
    prob = piso + (1.0 - piso) * e
    # un numero «aleatorio» fijo por palabra: mismo video, mismo reparto
    r = ((i * 2654435761 + semilla * 40503) >> 7) % 1000 / 1000.0
    return r < prob


if __name__ == '__main__':
    # tramo rapido (0-4 s, 4 palabras/s) y tramo calmado (6-14 s, 1 palabra cada 2 s)
    pal = [{'start': k * 0.25, 'end': k * 0.25 + 0.2} for k in range(16)] + [{'start': 6 + k * 2.0, 'end': 6.3 + k * 2.0} for k in range(5)]
    e = energia_de_palabras(pal)
    assert np.mean(e[:16]) > 0.7 and np.mean(e[16:]) < 0.3, (np.mean(e[:16]), np.mean(e[16:]))
    suena_rapido = sum(deja_pasar(e, i) for i in range(16))
    suena_calmo = sum(deja_pasar(e, i) for i in range(16, 21))
    assert suena_rapido >= 12, suena_rapido
    print('ok', round(float(np.mean(e[:16])), 2), round(float(np.mean(e[16:])), 2), suena_rapido, suena_calmo)
