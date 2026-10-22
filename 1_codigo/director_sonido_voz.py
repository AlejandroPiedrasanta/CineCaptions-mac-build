# CineCaptions · By Cinema Productions
# 1_codigo/director_sonido_voz.py — «AI Sound Director»: diagnóstico de la voz y su restauración (una COPIA), con guardas para que nunca suene robótica.
"""
REGLA DE ORO: NATURAL VOICE > ZERO NOISE. Un poco de ruido natural antes que una voz metálica.

`analizar(ruta, segmentos, palabras)`  una pasada por el audio (tiempo del timeline): suelo de ruido, SNR, hum 50/60 Hz y armónicos, hiss, rumble,
                                       viento, resonancia de sala, plosivas, sibilancia, aspereza, equilibrio tonal (contra el LTASS de Byrne),
                                       nivel desigual, clipping, inteligibilidad 1–4 kHz, LUFS / LRA / true peak, tipo de estéreo → `diagnostico`
`restaurar(ruta, destino, …)`          elige el BACKEND (VoiceRestorationBackend) según el `noise_score`, prueba la cadena en extractos y la compara
                                       ANTES/DESPUÉS (artefactos metálicos o robóticos, huecos espectrales, pérdida de agudos, de inteligibilidad,
                                       sobrecompresión): si DESPUÉS es peor, menos proceso; si sigue peor, el original. Luego la copia entera en WAV.

Niveles (RESTAURACION):  0 nada (la voz ya está limpia)  ·  1 PyAV / filtros de ffmpeg (afftdn, highpass, equalizer, deesser, acompressor, alimiter,
adeclip)  ·  2 RNNoise (`arnndn`) solo con un modelo validado en RNNOISE_MODELOS (calidad + licencia; hoy ninguno)  ·  3 un backend avanzado
externo (DeepFilterNet u otro) registrado con `registrar_backend` (hoy ninguno; nada se instala).
Audio ya MEZCLADO (voz + música en la misma pista): estrategia conservadora (sin reducción de ruido de voz aislada).
"""
import math
import time
from pathlib import Path

import numpy as np

import director_sonido_medir as M

# LTASS (Byrne et al. 1994, voz media, tercios de octava) relativo a 1 kHz: la referencia del equilibrio tonal de una voz natural (aproximada)
LTASS = {125: 4.8, 160: 3.9, 200: 5.3, 250: 6.9, 315: 7.2, 400: 6.3, 500: 5.7, 630: 3.7, 800: 2.5, 1000: 0.0, 1250: -1.3, 1600: -1.1, 2000: -3.7,
         2500: -5.1, 3150: -6.1, 4000: -6.9, 5000: -8.5, 6300: -10.3, 8000: -11.3}
OBJETIVO_LUFS = (-18.0, -12.0)        # la voz sola: si está fuera de esta ventana se lleva al borde; dentro, conserva su nivel (los SFX ya la siguen)
LIMITE_DBFS = -2.0                    # el limitador (muestra); el true peak queda ≤ −1 dBTP (se comprueba y, si no, se recorta)
TOPE_TP = -1.0
VERSION_CADENA = 3
UMBRAL_EFIMEROS = 3.0                 # picos sueltos por marco de más en el fondo = ruido musical (calibrado en probar_director_sonido)
RNNOISE_MODELOS = {}                  # {'nombre.rnnn': {'licencia': …, 'validado': True}}: vacío = el nivel 2 no se usa
_BACKENDS_EXTERNOS = []               # nivel 3: objetos con nombre, disponible() y procesar(origen_wav, destino_wav)


# ------------------------------------------------------------------------------------------------------------------------------ análisis
def analizar(ruta, segmentos=None, palabras=None, extractos=None):
    """Una pasada. Devuelve (diagnostico, medidas, guardados) — `guardados` son los extractos pedidos [(ini_s, fin_s)] ya decodificados
    (para probar la cadena sin volver a leer el archivo)."""
    t0 = time.time()
    recortes = {}
    A = M.Analizador(palabras=palabras)
    S = M.Sonometro(2)
    canales = None
    guardados = {tuple(e): [] for e in (extractos or [])}
    pos = 0
    for tr in M.trozos(ruta, segmentos=segmentos, recortes=recortes):
        if canales is None:
            canales = tr.shape[0]
        A.alimentar(tr)
        S.medir(tr if tr.shape[0] == 2 else np.vstack((tr, tr)))
        fin = pos + tr.shape[1]
        for (a, b), lista in guardados.items():
            ia, ib = int(a * M.SR), int(b * M.SR)
            if ib > pos and ia < fin:
                lista.append(tr[:, max(ia, pos) - pos:min(ib, fin) - pos])
        pos = fin
    medidas = A.resultado()
    medidas['loudness'] = S.resultado()
    medidas['recortes'] = recortes
    medidas['canales'] = canales or 1
    diag = diagnostico(medidas)
    diag['segundos_analisis'] = round(time.time() - t0, 2)
    return diag, medidas, {k: (np.concatenate(v, axis=1) if v else None) for k, v in guardados.items()}


def _potencia_media_db(v):
    v = np.asarray(v, dtype=np.float64)
    return float(10 * np.log10(np.mean(10 ** (v / 10.0)))) if v.size else -120.0


def _hum(esp, f):
    """El hum de la red (50 o 60 Hz) y sus armónicos: prominencia (dB) de cada pico sobre su entorno."""
    mejor = None
    for f0 in (50.0, 60.0):
        picos = []
        for k in range(1, 6):
            c = f0 * k
            i = int(np.argmin(np.abs(f - c)))
            pico = float(M.db(esp[max(0, i - 1):i + 2].max()))
            entorno = np.concatenate((esp[max(0, i - 8):max(0, i - 3)], esp[i + 3:i + 8]))
            base = float(M.db(np.median(entorno))) if entorno.size else pico
            picos.append((c, round(pico - base, 1)))
        fuerza = float(np.mean([p for _c, p in picos[:3]]))
        if mejor is None or fuerza > mejor['fuerza_db']:
            mejor = {'hz': f0, 'fuerza_db': round(fuerza, 1), 'armonicos': [c for c, p in picos if p >= 6.0]}
    return mejor


def _tercios_rel(esp, f):
    """Tercios de octava del espectro de la voz relativos a 1 kHz, al lado del LTASS."""
    t = dict(M.tercios(esp, f, 125, 8000))
    ref = min(t, key=lambda c: abs(c - 1000))
    return {int(round(min(LTASS, key=lambda x: abs(x - c)))): round(v - t[ref], 1) for c, v in t.items()}


def _huecos(m):
    """Marcos de 20 ms en el CENTRO de los huecos entre palabras (hueco ≥ 80 ms, a ≥ 30 ms de cada palabra): el fondo cuando casi no hay silencios."""
    rms = m['rms_db']
    t = (np.arange(rms.size) * M.MARCO + M.MARCO / 2) / M.SR
    sel = np.zeros(rms.size, bool)
    pal = m.get('palabras') or []
    for (a0, b0), (a1, _b1) in zip(pal, pal[1:]):
        if a1 - b0 >= 0.08:
            sel |= (t >= b0 + 0.03) & (t <= a1 - 0.03)
    return sel


def _fondo(m, nivel_voz):
    """El fondo (lo que suena cuando no se habla): nivel, bandas, planitud (tonal = música, liso = ruido) y de dónde se midió."""
    rms, cl = m['rms_db'], m['clase20']
    bandas = m['bandas_db']
    sil = (cl == 0) & (rms > -110)
    huecos = _huecos(m) & (rms > -110) if m.get('palabras') else np.zeros(rms.size, bool)
    if sil.sum() >= 15:
        sel, fuente = sil | huecos, 'silencios entre frases'
    elif huecos.sum() >= 8:
        sel, fuente = huecos, 'huecos entre palabras (casi no hay silencios)'
    else:
        validos = rms > -110
        sel = validos & (rms <= (np.percentile(rms[validos], 5) if validos.any() else -100))
        fuente = 'percentil 5 (sin silencios ni huecos)'
    if not sel.any():
        return {'nivel_db': -100.0, 'fuente': fuente, 'bandas': {}, 'planitud': 1.0, 'rel_voz_db': -100.0, 'graves_rel_voz_db': None,
                'n_silencio': int(sil.sum()), 'n_huecos': int(huecos.sum()), 'n': 0}
    nivel = float(np.percentile(rms[sel], 25 if fuente.startswith('huecos') else 50))
    bf = {n: _potencia_media_db(bandas[sel, i]) for i, n in enumerate(M.NOMBRES_BANDAS)} if bandas.size else {}
    plan = float(np.median(m['planitud20'][sel])) if m.get('planitud20') is not None and m['planitud20'].size == rms.size else 1.0
    graves_rel = None
    if bandas.size and (cl == 2).any():
        gv = _potencia_media_db(M.db(10 ** (bandas[cl == 2, 0] / 10) + 10 ** (bandas[cl == 2, 1] / 10)))
        gf = float(M.db(10 ** (bf['sub'] / 10) + 10 ** (bf['graves'] / 10)))
        graves_rel = round(gf - gv, 1)
    return {'nivel_db': round(nivel, 1), 'fuente': fuente, 'bandas': {k: round(v, 1) for k, v in bf.items()}, 'planitud': round(plan, 3),
            'rel_voz_db': round(float(np.median(rms[sel])) - nivel_voz, 1), 'graves_rel_voz_db': graves_rel,
            'n_silencio': int(sil.sum()), 'n_huecos': int(huecos.sum()), 'n': int(sel.sum())}


def diagnostico(m):
    """Lo que le pasa a la voz, con números y su lectura."""
    rms, clase = m['rms_db'], m['clase20']
    bandas = m['bandas_db']
    B = {n: bandas[:, i] for i, n in enumerate(M.NOMBRES_BANDAS)} if bandas.size else {}
    voz = rms[clase == 2]
    hay_voz = voz.size >= 25
    nivel_voz = _potencia_media_db(voz) if hay_voz else float(m.get('alto', -60))
    fondo = _fondo(m, nivel_voz)
    suelo = fondo['nivel_db']
    snr = nivel_voz - suelo
    f = m['f_fino']
    esp_v, esp_s = m['espectro'].get(2), m['espectro'].get(0)
    n_v, n_s = m['n_espectro'].get(2, 0), m['n_espectro'].get(0, 0)
    esp_hum = esp_s if n_s >= 5 else (m['espectro'].get(1) + esp_v if esp_v is not None and m['espectro'].get(1) is not None else esp_v)
    d = {'nivel_voz_db': round(nivel_voz, 1), 'suelo_ruido_db': round(suelo, 1), 'fuente_suelo': fondo['fuente'], 'snr_db': round(snr, 1),
         'fondo': fondo, 'segundos_voz': round(voz.size * M.MARCO / M.SR, 1), 'segundos_silencio': round(fondo['n_silencio'] * M.MARCO / M.SR, 1),
         'duracion': round(m['duracion'], 2), 'loudness': m.get('loudness'), 'problemas': []}
    # hum (un tono fijo: se ve en cualquier espectro medio)
    hum = _hum(esp_hum, f) if esp_hum is not None else None
    d['hum'] = hum
    if hum and hum['fuerza_db'] >= 8.0 and suelo > -85:
        d['problemas'].append(f"hum {int(hum['hz'])} Hz (+{hum['fuerza_db']} dB, armónicos {hum['armonicos']})")
    # hiss, rumble y viento: en el FONDO (silencios o, si casi no hay, los huecos entre palabras)
    fb = fondo['bandas']
    if fb:
        d['hiss_db'] = round(fb['brillo'], 1)
        d['hiss'] = bool(fb['brillo'] > -80 and fb['brillo'] - fb['medio'] > -6 and fondo['planitud'] > 0.3)
        if d['hiss']:
            d['problemas'].append(f"hiss (agudos del fondo {fb['brillo']:.0f} dBFS)")
    gf, mf, clf = m.get('graves_fino'), m.get('medio_fino'), m['clase_fina'][:len(m.get('graves_fino') if m.get('graves_fino') is not None else [])]
    if gf is not None and gf.size and clf.size == gf.size:
        fondo_f = clf == 0
        if fondo_f.sum() >= 3:                                     # graves del fondo con resolución de 5,9 Hz (20–150 Hz contra 300–3000 Hz)
            rel = _potencia_media_db(gf[fondo_f]) - _potencia_media_db(mf[fondo_f])
            d['rumble_rel_db'] = round(rel, 1)
            d['rumble'] = bool(rel > 0 and _potencia_media_db(gf[fondo_f]) > -75)
            if d['rumble']:
                d['problemas'].append(f'rumble (graves del fondo {rel:+.0f} dB sobre los medios)')
        golpes = (gf > mf + 6) & (gf > suelo + 15)                 # viento: ráfagas de graves que tapan los medios
        d['viento_frac'] = round(float(golpes.mean()), 4)
        d['viento'] = bool(d['viento_frac'] > 0.05)
        if d['viento']:
            d['problemas'].append(f"viento ({100 * d['viento_frac']:.0f} % de los marcos con ráfagas de graves)")
    # voz: equilibrio tonal, resonancias, aspereza, sibilancia, plosivas, nivel desigual
    if esp_v is not None and n_v >= 5:
        rel = _tercios_rel(esp_v, f)
        dev = {c: round(rel[c] - LTASS[c], 1) for c in rel if c in LTASS}
        d['equilibrio'] = dev
        barro = np.mean([dev[c] for c in (250, 315, 400, 500) if c in dev])
        aspereza = np.mean([dev[c] for c in (2500, 3150, 4000) if c in dev])
        aire = np.mean([dev[c] for c in (6300, 8000) if c in dev])
        presencia = np.mean([dev[c] for c in (2000, 2500, 3150) if c in dev])
        d['barro_db'], d['aspereza_db'], d['aire_db'], d['presencia_db'] = (round(float(x), 1) for x in (barro, aspereza, aire, presencia))
        if barro > 4:
            d['problemas'].append(f'voz con barro (+{barro:.0f} dB en 250–500 Hz)')
        if aspereza > 4:
            d['problemas'].append(f'voz áspera (+{aspereza:.0f} dB en 2,5–4 kHz)')
        if aire < -9:
            d['problemas'].append(f'voz apagada ({aire:.0f} dB de aire)')
        t = M.tercios(esp_v, f, 100, 700)
        f0 = m.get('f0')
        d['f0_hz'] = f0
        res = []
        for k in range(2, len(t) - 2):
            vecinos = np.mean([t[k - 2][1], t[k - 1][1], t[k + 1][1], t[k + 2][1]])
            c = t[k][0]
            de_la_voz = f0 is not None and any(abs(c - h * f0) <= 0.3 * h * f0 for h in (1, 2, 3))
            if t[k][1] - vecinos > 6.0 and not de_la_voz:           # la F0 de la voz y sus armónicos no son una sala
                res.append((c, round(t[k][1] - vecinos, 1)))
        d['resonancias'] = res
        if res:
            d['problemas'].append('resonancia de sala en ' + ', '.join(f'{int(c)} Hz' for c, _x in res[:2]))
    if B and hay_voz:
        sib = float(np.percentile(B['sibilancia'][clase == 2], 95)) - float(np.percentile(rms[clase == 2], 90))
        d['sibilancia_p95_db'] = round(sib, 1)                   # las eses (5–9 kHz, p95) respecto a las vocales (nivel p90 de la voz)
        d['sibilancia'] = 'alta' if sib > -3 else ('media' if sib > -8 else 'normal')
        if d['sibilancia'] != 'normal':
            d['problemas'].append(f"sibilancia {d['sibilancia']} (p95 {d['sibilancia_p95_db']:+.0f} dB)")
        graves = M.db(10 ** (B['sub'] / 10) + 10 ** (B['graves'] / 10))
        salto = np.diff(graves, prepend=graves[:1])
        cerca_voz = np.convolve((clase == 2).astype(float), np.ones(5), 'same') > 0
        plos = (salto > 12) & (graves > nivel_voz - 6) & cerca_voz
        d['plosivas_min'] = round(float(plos.sum()) / max(1e-6, m['duracion'] / 60.0), 1)
        if d['plosivas_min'] > 6:
            d['problemas'].append(f"plosivas ({d['plosivas_min']:.0f}/min)")
        ventanas = []
        for i in range(0, rms.size - 25, 25):                      # 0,5 s
            sel = clase[i:i + 25] == 2
            if sel.mean() >= 0.6:
                ventanas.append(_potencia_media_db(rms[i:i + 25][sel]))
        d['estabilidad_db'] = round(float(np.std(ventanas)), 1) if len(ventanas) >= 4 else None
        d['desigual'] = bool(d['estabilidad_db'] is not None and d['estabilidad_db'] > 4.5)
        if d['desigual']:
            d['problemas'].append(f"nivel desigual (±{d['estabilidad_db']} dB entre frases)")
        if fb:
            voz_1_4 = _potencia_media_db(M.db(10 ** (B['m1'][clase == 2] / 10) + 10 ** (B['m2'][clase == 2] / 10)))
            snr_1_4 = voz_1_4 - float(M.db(10 ** (fb['m1'] / 10) + 10 ** (fb['m2'] / 10)))
            d['snr_1_4k_db'] = round(snr_1_4, 1)
            d['inteligibilidad'] = round(float(np.clip((snr_1_4 + 15) / 30.0, 0, 1)), 3)
    rec = m.get('recortes') or {}
    pct = 100.0 * rec.get('recortadas', 0) / max(1, rec.get('muestras', 1))
    d['clipping'] = {'tramos': int(rec.get('tramos', 0)), 'porcentaje': round(pct, 4), 'pico': round(float(rec.get('pico', 0.0)), 4)}
    if rec.get('tramos', 0) > 3 or pct > 0.005:
        d['problemas'].append(f"clipping ({rec.get('tramos', 0)} tramos, {pct:.3f} %)")
    lo = m.get('loudness') or {}
    if lo.get('tp_db') is not None and lo['tp_db'] > TOPE_TP:
        d['problemas'].append(f"true peak alto ({lo['tp_db']:+.1f} dBTP)")
    est = m.get('estereo')
    if m.get('canales', 1) == 1 or not est:
        d['estereo'] = 'mono'
    elif abs(est['dif_db']) > 25:
        d['estereo'] = 'un_canal'
    elif est['correlacion'] > 0.97 and abs(est['dif_db']) < 1.5:
        d['estereo'] = 'dual_mono'
    else:
        d['estereo'] = 'estereo'
    d['correlacion_lr'] = round(est['correlacion'], 3) if est else None
    # noise_score 0–1: cuánto estorba el fondo (del SNR, el hum, el hiss, el viento)
    ns = float(np.clip((40.0 - snr) / 30.0, 0, 1))
    if hum and hum['fuerza_db'] >= 8.0:
        ns = max(ns, min(1.0, 0.25 + hum['fuerza_db'] / 40.0))
    if d.get('hiss'):
        ns = min(1.0, ns + 0.1)
    if d.get('viento'):
        ns = min(1.0, ns + 0.2)
    d['noise_score'] = round(ns, 3)
    d['ruido'] = 'bajo' if ns < 0.2 else ('moderado' if ns < 0.5 else 'alto')
    return d


# ------------------------------------------------------------------------------------------------------------------------------ backends
class Backend:
    """VoiceRestorationBackend: `nivel`, `nombre`, `disponible()` y `cadena(diag, fuerza)` → [(filtro de ffmpeg, opciones, por qué)]."""
    nivel, nombre = 0, 'ninguno'

    def disponible(self):
        return True

    def cadena(self, diag, fuerza=1.0, mezclada=False):
        return []


class Nivel0(Backend):
    nivel, nombre = 0, 'sin proceso'


class NivelPyAV(Backend):
    """Nivel 1: los filtros de ffmpeg que trae PyAV. Cada etapa solo si el diagnóstico la pide; `fuerza` (0–1) la suaviza al reintentar."""
    nivel, nombre = 1, 'PyAV'

    def cadena(self, diag, fuerza=1.0, mezclada=False, con_nr=True):
        c = []
        clip = diag.get('clipping') or {}
        if clip.get('tramos', 0) > 3 or clip.get('porcentaje', 0) > 0.005:
            c.append(('adeclip', 'w=55:o=75:a=8:t=10:n=1000', 'clipping: se reconstruyen los picos recortados'))
        hum = diag.get('hum') or {}
        if hum.get('fuerza_db', 0) >= 8.0:
            for k, armonico in enumerate([hum['hz'] * i for i in (1, 2, 3, 4)]):
                if k == 0 or armonico in (hum.get('armonicos') or []):
                    g = -min(24.0, hum['fuerza_db'] + 6.0) * (0.6 + 0.4 * fuerza)
                    c.append(('equalizer', f'f={armonico:.0f}:t=q:w=12:g={g:.1f}', f'hum: muesca estrecha en {armonico:.0f} Hz'))
        if mezclada:                                                 # con la música dentro, el paso alto se comería su bajo: solo lo subsónico
            c.append(('highpass', 'f=35:p=2', 'solo lo subsónico (35 Hz): la música mezclada conserva su bajo'))
        else:
            hp = 70
            if diag.get('rumble') or diag.get('viento'):
                hp = 95
            elif (diag.get('plosivas_min') or 0) > 6:
                hp = 85
            c.append(('highpass', f'f={hp}:p=2', f'paso alto a {hp} Hz (graves que no son voz)'))
            if diag.get('rumble') or diag.get('viento'):
                c.append(('highpass', f'f={hp}:p=2', 'segundo paso alto (24 dB/oct) por rumble o viento'))
        snr = float(diag.get('snr_db') or 60.0)
        if con_nr and not mezclada:
            nr = 0.0 if snr >= 38 else (6.0 if snr >= 30 else (9.0 if snr >= 22 else (12.0 if snr >= 15 else 15.0)))
            if diag.get('tope_nr') is not None and nr > diag['tope_nr']:
                nr = float(diag['tope_nr'])                          # el ambiente decidió conservar el lugar: solo se quita lo que compite
            nr *= fuerza
            if nr >= 3.0:
                c.append(('nr_espectral', f'reduccion={nr:.1f}', f'reducción de ruido con tope de {nr:.0f} dB (SNR {snr:.0f} dB): natural antes que cero ruido'))
        barro = diag.get('barro_db') or 0.0
        if barro > 4 and not mezclada:
            c.append(('equalizer', f'f=350:t=o:w=1:g={-min(4.0, barro - 2.0) * fuerza:.1f}', f'menos barro ({barro:+.0f} dB en 250–500 Hz)'))
        for hz, cuanto in (diag.get('resonancias') or [])[:2]:
            if not mezclada:
                c.append(('equalizer', f'f={hz:.0f}:t=q:w=6:g={-min(6.0, cuanto) * fuerza:.1f}', f'resonancia de sala en {hz:.0f} Hz'))
        asp = diag.get('aspereza_db') or 0.0
        if asp > 4:
            c.append(('equalizer', f'f=3200:t=o:w=1:g={-min(3.0, asp - 2.0) * fuerza:.1f}', f'menos aspereza ({asp:+.0f} dB en 2,5–4 kHz)'))
        sib = diag.get('sibilancia')
        if sib in ('media', 'alta'):
            i = (0.5 if sib == 'alta' else 0.3) * (0.5 + 0.5 * fuerza)
            c.append(('deesser', f'i={i:.2f}:m=0.5:f=0.5:s=o', f'de-esser ({sib})'))
        nivel = float(diag.get('nivel_voz_db') or -30.0)
        desigual = bool(diag.get('desigual'))
        lra = (diag.get('loudness') or {}).get('lra')
        ya_comprimida = (lra is not None and lra < 3.0) or (diag.get('estabilidad_db') is not None and diag['estabilidad_db'] < 2.0 and not desigual)
        ruidosa = float(diag.get('snr_db') or 60.0) < 20.0 and not desigual   # con SNR < 20 dB comprimir sube el ruido entre sílabas (sin nivel desigual no compensa)
        if not ya_comprimida and not mezclada and not ruidosa:      # ya comprimida: no se aplasta más; con la música dentro, comprimir la subiría entre palabras
            ratio = (1.5 if mezclada else (3.0 if desigual else 2.0)) * (0.7 + 0.3 * fuerza)
            umbral = 10 ** ((nivel + (6.0 if mezclada else 2.0)) / 20.0)
            c.append(('acompressor', f'threshold={max(0.001, min(1.0, umbral)):.4f}:ratio={max(1.2, ratio):.2f}:attack=12:release=180:knee=4:detection=rms:link=average',
                      f'compresión suave {max(1.2, ratio):.1f}:1' + (' (nivel desigual)' if desigual else '')))
        if not mezclada:
            pres = diag.get('presencia_db') or 0.0
            if pres < -4:
                c.append(('equalizer', f'f=3500:t=o:w=1.2:g={min(2.5, -pres - 2.0) * fuerza:.1f}', 'un poco más de presencia (claridad)'))
            aire = diag.get('aire_db') or 0.0
            if aire < -6 and not diag.get('hiss'):
                c.append(('highshelf', f'f=9000:g={min(2.0, -aire - 4.0) * fuerza:.1f}', 'un poco de aire'))
        return c


class NivelRNNoise(NivelPyAV):
    """Nivel 2: RNNoise (`arnndn`) en lugar de afftdn, SOLO con un modelo validado (RNNOISE_MODELOS)."""
    nivel, nombre = 2, 'RNNoise'

    def modelo(self):
        carpeta = Path(__file__).resolve().parent.parent / '2_recursos' / 'sound_director' / 'rnnoise'
        for nombre, datos in RNNOISE_MODELOS.items():
            if datos.get('validado') and (carpeta / nombre).is_file():
                return carpeta / nombre
        return None

    def disponible(self):
        return self.modelo() is not None

    def cadena(self, diag, fuerza=1.0, mezclada=False):
        c = super().cadena(diag, fuerza, mezclada, con_nr=False)
        if not mezclada:
            mix = 0.85 * fuerza
            ruta = str(self.modelo()).replace('\\', '/').replace(':', '\\:')
            c.insert(1, ('arnndn', f"m='{ruta}':mix={mix:.2f}", f'RNNoise (mezcla {mix:.0%})'))
        return c


class NivelAvanzado(Backend):
    """Nivel 3: interfaz para un restaurador externo (DeepFilterNet u otro). Solo existe si alguien lo registró y está disponible."""
    nivel, nombre = 3, 'avanzado'

    def externo(self):
        return next((b for b in _BACKENDS_EXTERNOS if getattr(b, 'disponible', lambda: False)()), None)

    def disponible(self):
        return self.externo() is not None


def registrar_backend(backend):
    """Nivel 3 (futuro): `backend` con nombre, disponible() y procesar(origen_wav, destino_wav)."""
    _BACKENDS_EXTERNOS.append(backend)


def necesita_proceso(diag):
    """¿Hay algo que mejorar? (si no, NIVEL 0: la voz ya está limpia y a buen nivel)."""
    lufs = (diag.get('loudness') or {}).get('lufs')
    fuera = lufs is not None and not (OBJETIVO_LUFS[0] - 1.0 <= lufs <= OBJETIVO_LUFS[1] + 1.0)
    return bool(diag.get('problemas')) or diag.get('noise_score', 0) >= 0.2 or fuera


def elegir_backend(diag, mezclada=False):
    """La IA decide cuánto proceso: limpia → nivel 0; poco o medio ruido → nivel 1; mucho → el mejor disponible (3 → 2 → 1). (backend, por qué)"""
    if not necesita_proceso(diag):
        return Nivel0(), 'la voz ya está limpia y a buen nivel'
    ns = diag.get('noise_score', 0.0)
    if mezclada:
        return NivelPyAV(), 'voz y música ya mezcladas: estrategia conservadora con los filtros de PyAV'
    if ns >= 0.5:
        for b in (NivelAvanzado(), NivelRNNoise()):
            if b.disponible():
                return b, f'ruido alto (noise_score {ns:.2f}): {b.nombre}'
        return NivelPyAV(), f'ruido alto (noise_score {ns:.2f}): PyAV (no hay backend superior instalado; reducción con tope para que no suene robótica)'
    return NivelPyAV(), f"ruido {diag.get('ruido')} (noise_score {ns:.2f}): PyAV"


# ------------------------------------------------------------------------------------------------------------------------------ proceso
def _etapas(cadena, canales, ganancia_db=None):
    """La cadena como etapas: los filtros de ffmpeg seguidos van en un grafo; 'nr_espectral' es la reducción de ruido de director_sonido_nr."""
    import director_sonido_nr as NR
    filtros = [(f, o) for f, o, _p in cadena]
    if ganancia_db is not None:
        filtros += [('volume', f'{ganancia_db:.2f}dB'), ('alimiter', f'limit={10 ** (LIMITE_DBFS / 20):.4f}:attack=5:release=60:level=false:latency=1')]
    etapas, grupo = [], []
    for f, o in filtros:
        if f == 'nr_espectral':
            if grupo:
                etapas.append(M.Grafo(grupo, canales))
                grupo = []
            op = dict(x.split('=') for x in o.split(':'))
            etapas.append(NR.ReductorEspectral(canales, reduccion_db=float(op['reduccion']), alfa_dd=float(op.get('dd', NR.ALFA_DD)),
                                               suavizar=op.get('suave', '1') != '0'))
        else:
            grupo.append((f, o))
    if grupo:
        etapas.append(M.Grafo(grupo, canales))
    return etapas


def _procesar_trozos(origen, cadena, canales, ganancia_db=None, medir=True, info=None):
    """Pasa los trozos por la cadena (+ ganancia y limitador si se da `ganancia_db`). Genera los trozos procesados; al acabar, `info['loudness']`."""
    etapas = _etapas(cadena, canales, ganancia_db)
    S = M.Sonometro(2) if medir else None

    def salir(y):
        if y.shape[1] and S:
            S.medir(y if y.shape[0] == 2 else np.vstack((y, y)))
        return y
    for tr in origen:
        y = tr
        for e in etapas:
            y = e.empujar(y) if y.shape[1] else y
        if y.shape[1]:
            yield salir(y)
    for i, e in enumerate(etapas):                                   # vaciar cada etapa por las que siguen
        y = e.terminar()
        for e2 in etapas[i + 1:]:
            y = e2.empujar(y) if y.shape[1] else y
        if y.shape[1]:
            yield salir(y)
    if info is not None:
        info['loudness'] = S.resultado() if S else None


def _a_canales(tr, estereo):
    """La voz en la forma en que se procesa: un solo canal útil → mono (y luego dual mono); estéreo de verdad → estéreo."""
    if estereo == 'un_canal' and tr.shape[0] == 2:
        e = (tr ** 2).sum(axis=1)
        return tr[[int(np.argmax(e))]]
    if estereo in ('dual_mono', 'mono') and tr.shape[0] == 2:
        return tr.mean(axis=0, keepdims=True)
    return tr


def _trozos_de(x, n=M.SR * 4):
    for i in range(0, x.shape[1], n):
        yield x[:, i:i + n]


def comparar(antes, despues, diag, cadena):
    """Las guardas ANTES/DESPUÉS (mismos marcos). Devuelve {'peor': bool, 'motivos': [...], 'medidas': {...}}."""
    f = antes['f_fino']
    motivos, med = [], {}
    ev_a, ev_d = antes['espectro'].get(2), despues['espectro'].get(2)
    es_a, es_d = antes['espectro'].get(0), despues['espectro'].get(0)
    hay_sil = antes['n_espectro'].get(0, 0) >= 5
    if ev_a is None or ev_d is None or antes['n_espectro'].get(2, 0) < 5:
        return {'peor': False, 'motivos': ['sin voz suficiente para comparar'], 'medidas': {}}
    ta, td = dict(M.tercios(ev_a, f, 100, 10000)), dict(M.tercios(ev_d, f, 100, 10000))
    dif = {c: td[c] - ta[c] for c in ta}
    mediana = float(np.median([dif[c] for c in dif if 300 <= c <= 4000]))
    hp = max([float(o.split('f=')[1].split(':')[0]) for fl, o, _p in cadena if fl == 'highpass'] or [0.0])
    muescas = [float(o.split('f=')[1].split(':')[0]) for fl, o, _p in cadena if fl == 'equalizer' and ':t=q' in o]
    # solo cuentan las bandas donde manda la VOZ (≥ 10 dB sobre el fondo): si una banda era sobre todo ruido o hum, que baje es justo lo buscado
    fondo_t = dict(M.tercios(es_a, f, 100, 10000)) if (hay_sil and es_a is not None) else {}
    de_la_voz = {c for c in ta if c not in fondo_t or ta[c] - fondo_t[c] >= 10.0}
    med['bandas_de_la_voz'] = len(de_la_voz)
    huecos = [(round(c), round(dif[c] - mediana, 1)) for c in dif
              if c in de_la_voz and c > hp * 1.6 and all(abs(c - m) > m * 0.25 for m in muescas) and dif[c] - mediana < -9.0]
    med['huecos'] = huecos
    if huecos:
        motivos.append('huecos espectrales en ' + ', '.join(f'{c} Hz' for c, _x in huecos[:3]))
    agudos = float(np.mean([dif[c] for c in dif if 6000 <= c <= 10000 and c in de_la_voz] or [0.0])) - mediana
    med['perdida_agudos_db'] = round(agudos, 1)
    tope_agudos = -7.0 if any(fl == 'deesser' for fl, _o, _p in cadena) else -5.0
    if agudos < tope_agudos:
        motivos.append(f'pierde agudos ({agudos:.1f} dB en 6–10 kHz)')
    if hay_sil and es_a is not None and es_d is not None:
        snr_a = M.banda_db(ev_a, f, 1000, 4000) - M.banda_db(es_a, f, 1000, 4000)
        snr_d = M.banda_db(ev_d, f, 1000, 4000) - M.banda_db(es_d, f, 1000, 4000)
        med['snr_1_4k_antes'], med['snr_1_4k_despues'] = round(snr_a, 1), round(snr_d, 1)
        if snr_d < snr_a - 1.0:
            motivos.append(f'pierde inteligibilidad (SNR 1–4 kHz {snr_a:.0f} → {snr_d:.0f} dB)')
    # ruido «musical» (lo metálico de una mala reducción): picos sueltos que aparecen y desaparecen en el FONDO (silencios o huecos entre palabras)
    fondo = (antes['clase20'] == 0) | (_huecos(antes) if antes.get('palabras') else False)
    ea, ed = antes.get('efimeros'), despues.get('efimeros')
    if ea is not None and ed is not None and ea.size and ed.size:
        n = min(ea.size, ed.size, fondo.size)
        sel = fondo[:n] & (antes['rms_db'][:n] > -100)
        if sel.sum() >= 5:
            m_a, m_d = float(np.mean(ea[:n][sel])), float(np.mean(ed[:n][sel]))
            med['ruido_musical'] = {'picos_efimeros_antes': round(m_a, 2), 'picos_efimeros_despues': round(m_d, 2)}
            if m_d > m_a + UMBRAL_EFIMEROS:
                motivos.append(f'ruido musical en el fondo (picos sueltos {m_a:.1f} → {m_d:.1f} por marco)')
    # la voz no puede quedar entrecortada ni deformada: su envolvente (nivel de cada marco de 20 ms) tiene que seguir siendo la misma DONDE MANDA LA
    # VOZ (≥ 12 dB sobre el fondo); los valles entre sílabas que eran ruido SÍ se hacen más hondos al limpiar (eso es lo buscado, no un artefacto)
    # (en la banda de la voz, 500 Hz–4 kHz: el viento, el rumble o un DC que quita el paso alto no son la voz)
    rms_a, rms_d = _banda_voz(antes), _banda_voz(despues)
    sel_fondo = fondo[:rms_a.size] & (antes['rms_db'][:rms_a.size] > -100) if isinstance(fondo, np.ndarray) else np.zeros(rms_a.size, bool)
    validos = rms_a > -100
    suelo = float(np.median(rms_a[sel_fondo])) if sel_fondo.sum() >= 5 else (float(np.percentile(rms_a[validos], 10)) if validos.any() else -100.0)
    voz_a = (antes['clase20'][:rms_a.size] == 2) & (rms_a >= suelo + 12.0)
    n = min(voz_a.size, rms_d.size)
    med['envolvente_marcos'] = int(voz_a[:n].sum())
    if voz_a[:n].sum() >= 50:
        ra, rd = rms_a[:n][voz_a[:n]], rms_d[:n][voz_a[:n]]
        corr = float(np.corrcoef(ra, rd)[0, 1]) if ra.std() > 0 and rd.std() > 0 else 1.0
        med['envolvente_voz_corr'] = round(corr, 4)                  # (informativa: con voces muy ruidosas baja aunque el proceso sea bueno)
        cambio = rd - ra
        caidas = float(np.mean(cambio - np.median(cambio) < -8.0))   # marcos con voz clara que pierden > 8 dB más que el resto = voz entrecortada
        med['voz_caidas_pct'] = round(100 * caidas, 2)
        if caidas > 0.05:
            motivos.append(f'voz entrecortada ({100 * caidas:.0f} % de los marcos con voz clara pierden más de 8 dB)')
    est_a = _estabilidad(antes)
    est_d = _estabilidad(despues, antes['clase20'])
    med['estabilidad_antes'], med['estabilidad_despues'] = est_a, est_d
    cresta_a, cresta_d = _cresta(antes), _cresta(despues, antes['clase20'])
    med['cresta_antes_db'], med['cresta_despues_db'] = cresta_a, cresta_d
    if est_a and est_d is not None and est_d < 0.45 * est_a and est_d < 1.5:
        motivos.append(f'sobrecompresión (variación entre frases {est_a} → {est_d} dB)')
    if cresta_a and cresta_d is not None and cresta_d < cresta_a - 6.0:
        motivos.append(f'sobrecompresión (cresta {cresta_a} → {cresta_d} dB)')
    return {'peor': bool(motivos), 'motivos': motivos, 'medidas': med}


def _banda_voz(m):
    """El nivel (dB) de cada marco de 20 ms en la banda de la voz (500 Hz–4 kHz: medio + m1 + m2)."""
    B = m['bandas_db']
    if not B.size:
        return m['rms_db']
    i = [M.NOMBRES_BANDAS.index(n) for n in ('medio', 'm1', 'm2')]
    return M.db(sum(10 ** (B[:, k].astype(np.float64) / 10.0) for k in i))


def _estabilidad(m, clase=None):
    rms, cl = m['rms_db'], (m['clase20'] if clase is None else clase[:m['rms_db'].size])
    v = []
    for i in range(0, min(rms.size, cl.size) - 25, 25):
        sel = cl[i:i + 25] == 2
        if sel.mean() >= 0.6:
            v.append(_potencia_media_db(rms[i:i + 25][sel]))
    return round(float(np.std(v)), 2) if len(v) >= 4 else None


def _cresta(m, clase=None):
    """Pico menos media (dB) de la voz por marcos de 20 ms: cuánta vida le queda a la dinámica corta."""
    rms, cl = m['rms_db'], (m['clase20'] if clase is None else clase[:m['rms_db'].size])
    n = min(rms.size, cl.size)
    v = rms[:n][cl[:n] == 2]
    return round(float(np.percentile(v, 98) - np.median(v)), 2) if v.size >= 25 else None


def _analizar_x(x, clase_fina=None, palabras=None):
    A = M.Analizador(palabras=palabras, clase_fina=clase_fina)
    for tr in _trozos_de(x):
        A.alimentar(tr)
    return A.resultado()


def probar_en_extractos(extractos, diag, backend, mezclada, palabras_ext=None):
    """La cadena en los extractos con fuerza 1 → 0,6 → 0,3 hasta que las guardas pasan. (cadena, fuerza, informe) o (None, None, informe)."""
    intentos = []
    for fuerza in (1.0, 0.6, 0.3):
        cadena = backend.cadena(diag, fuerza, mezclada)
        peor, motivos, medidas = False, [], []
        for k, (x, pal) in enumerate(zip(extractos, palabras_ext or [None] * len(extractos))):
            antes = _analizar_x(x, palabras=pal)
            if not pal:                                              # sin palabras la clase salió del nivel: se reaplica marco a marco (antes y después, mismos marcos)
                c20 = antes['clase20']
                antes = _analizar_x(x, clase_fina=antes['clase_fina'])
                antes['clase20'] = c20
            y = np.concatenate(list(_procesar_trozos(_trozos_de(x), cadena, x.shape[0], medir=False)) or [x[:, :0]], axis=1)
            y = _alinear(y, x.shape[1])
            despues = _analizar_x(y, clase_fina=antes['clase_fina'])
            despues['clase20'] = antes['clase20']
            r = comparar(antes, despues, diag, cadena)
            medidas.append(r['medidas'])
            if r['peor']:
                peor = True
                motivos += [f'extracto {k + 1}: {m}' for m in r['motivos']]
        intentos.append({'fuerza': fuerza, 'pasa': not peor, 'motivos': motivos, 'medidas': medidas})
        if not peor:
            return cadena, fuerza, intentos
    return None, None, intentos


def _alinear(y, n):
    """Mismo largo que el original (los filtros con latencia compensada no deberían cambiarlo; por si acaso)."""
    if y.shape[1] >= n:
        return y[:, :n]
    return np.concatenate((y, np.zeros((y.shape[0], n - y.shape[1]), np.float32)), axis=1)


def tope_por_ambiente(ambiente):
    """La reducción de ruido máxima que permite la decisión de AMBIENTE: conservar la calle, la gente o la naturaleza = solo quitar lo que compite
    con la voz (6 dB); reducirlo = 10 dB; limpiar / interior / nada = sin tope extra. (dB o None, y por qué)"""
    escenas = (ambiente or {}).get('escenas') or []
    reales = [e for e in escenas if e.get('decision') == 'KEEP_ORIGINAL_AMBIENCE' and e.get('contexto') not in ('QUIET_INTERIOR', 'INTERIOR', 'ROOM', 'OFFICE', 'STUDIO', 'MUSIC_BED')]
    if reales:
        return 6.0, f"se conserva el ambiente de {reales[0]['contexto'].lower()}: la reducción de ruido solo quita lo que compite con la voz (tope 6 dB)"
    if any(e.get('decision') == 'REDUCE_AMBIENCE' for e in escenas):
        return 10.0, 'el ambiente compite con la voz: se reduce (tope 10 dB)'
    return None, None


def _palabras_en(palabras, a, b):
    """Las palabras de la ventana [a, b) del timeline, con el tiempo desde el inicio de la ventana."""
    return [dict(p, start=float(p['start']) - a, end=float(p.get('end', p['start'])) - a) for p in (palabras or [])
            if isinstance(p, dict) and a <= float(p.get('start', 0)) < b]


def restaurar(ruta, destino, segmentos=None, palabras=None, diag=None, medidas=None, extractos=None, mezclada=False, al_estado=None, ambiente=None,
              ventanas=None):
    """La voz restaurada (COPIA en `destino`, WAV 24 bits, el mismo número de canales que el original para que suene igual de fuerte en Resolve).
    Devuelve {'archivo' | None, 'backend', 'nivel', 'cadena', 'motivo', 'antes', 'despues', 'guardas', 'segundos'}. Nunca toca el original."""
    t0 = time.time()
    if diag is None:
        diag, medidas, guardados = analizar(ruta, segmentos, palabras, extractos=elegir_extractos(segmentos, ruta))
        extractos = [v for v in guardados.values() if v is not None]
    tope, por_tope = tope_por_ambiente(ambiente)
    if tope is not None:
        diag = dict(diag, tope_nr=tope)
    backend, por_que = elegir_backend(diag, mezclada)
    if por_tope:
        por_que += ' · ' + por_tope
    salida = {'archivo': None, 'backend': backend.nombre, 'nivel': backend.nivel, 'cadena': [], 'motivo': por_que, 'antes': resumen_calidad(diag),
              'despues': None, 'guardas': None, 'segundos': 0.0, 'mezclada': bool(mezclada)}
    if backend.nivel == 0:
        salida['segundos'] = round(time.time() - t0, 2)
        return salida
    if backend.nivel == 3:                                            # (futuro) restaurador externo: no hay ninguno registrado hoy
        backend, salida['motivo'] = NivelPyAV(), por_que + ' · el externo no respondió: PyAV'
    estereo = diag.get('estereo', 'mono')
    ext = [_a_canales(x, estereo) for x in (extractos or []) if x is not None and x.shape[1] > M.SR]
    if al_estado:
        al_estado('AI Sound Director: probando la limpieza de la voz…')
    pal_ext = [_palabras_en(palabras, a, b) for a, b in ventanas] if (ventanas and palabras and len(ventanas) == len(ext)) else None
    cadena, fuerza, intentos = probar_en_extractos(ext, diag, backend, mezclada, pal_ext) if ext else (backend.cadena(diag, 1.0, mezclada), 1.0, [])
    salida['guardas'] = {'extractos': len(ext), 'intentos': intentos}
    if cadena is not None and not _sustancial(cadena, diag):
        salida.update({'nivel': 0, 'backend': 'sin proceso', 'segundos': round(time.time() - t0, 2),
                       'motivo': ('voz y música ya mezcladas y sin nada que se pueda arreglar sin tocar la música' if mezclada else
                                  'la voz no necesita nada que se oiga') + ': se queda la original'})
        return salida
    if cadena is None:
        salida['motivo'] = 'las guardas vieron artefactos incluso con el proceso más suave: se queda la voz original'
        salida['nivel'], salida['backend'] = 0, 'sin proceso (revertido)'
        salida['segundos'] = round(time.time() - t0, 2)
        return salida
    canales_proc = 1 if estereo in ('mono', 'dual_mono', 'un_canal') else 2
    if al_estado:
        al_estado('AI Sound Director: limpiando la voz…')
    # pasada A: lo que suena la cadena (para la ganancia final)
    info_a, info_b = {}, {}
    for _y in _procesar_trozos((_a_canales(t, estereo) for t in M.trozos(ruta, segmentos=segmentos)), cadena, canales_proc, info=info_a):
        pass
    lufs_cadena = (info_a.get('loudness') or {}).get('lufs')
    lufs_orig = (diag.get('loudness') or {}).get('lufs')
    objetivo = float(np.clip(lufs_orig if lufs_orig is not None else -16.0, *OBJETIVO_LUFS))
    ganancia = float(np.clip((objetivo - lufs_cadena) if lufs_cadena is not None else 0.0, -12.0, 18.0))
    # pasada B: la copia, con ganancia y limitador, escrita y medida
    canales_salida = 1 if (M.info(ruta) or {}).get('canales', 2) == 1 else 2
    tmp = Path(str(destino) + '.tmp.wav')
    W = M.EscritorWav(tmp, canales_salida)
    A = M.Analizador(clase_fina=medidas['clase_fina'] if medidas else None, palabras=palabras)     # (las palabras: el fondo se mide en los mismos huecos)
    try:
        for y in _procesar_trozos((_a_canales(t, estereo) for t in M.trozos(ruta, segmentos=segmentos)), cadena, canales_proc, ganancia_db=ganancia,
                                  info=info_b):
            if canales_salida == 2 and y.shape[0] == 1:
                y = np.vstack((y, y))
            W.escribir(y)
            A.alimentar(y)
    finally:
        W.cerrar()
    loud = info_b.get('loudness') or {}
    if loud.get('tp_db') is not None and loud['tp_db'] > TOPE_TP:   # el limitador trabaja por muestra: si un pico entre muestras pasa de −1 dBTP, se recorta
        recorte = TOPE_TP - 0.2 - loud['tp_db']
        tmp2 = Path(str(destino) + '.tmp2.wav')
        W2 = M.EscritorWav(tmp2, canales_salida)
        S2 = M.Sonometro(2)
        for y in M.leer_wav(tmp):
            y = y * (10 ** (recorte / 20))
            W2.escribir(y)
            S2.medir(y if y.shape[0] == 2 else np.vstack((y, y)))
        W2.cerrar()
        tmp.unlink()
        tmp2.replace(tmp)
        loud = S2.resultado()
        ganancia += recorte
    despues_m = A.resultado()
    despues_m['loudness'] = loud
    despues_m['canales'] = canales_salida
    if medidas is not None:
        despues_m['clase20'] = medidas['clase20'][:despues_m['rms_db'].size]
    diag_d = diagnostico(despues_m)
    antes_m = medidas
    if medidas is not None and not medidas.get('palabras'):          # sin palabras: el original otra vez con la MISMA clase marco a marco
        A2 = M.Analizador(clase_fina=medidas['clase_fina'])
        for t in M.trozos(ruta, segmentos=segmentos):
            A2.alimentar(_a_canales(t, estereo) if canales_proc == 1 else t)
        antes_m = A2.resultado()
        antes_m['clase20'] = medidas['clase20'][:antes_m['rms_db'].size]
    final = comparar(antes_m, despues_m, diag, cadena) if antes_m is not None else {'peor': False, 'motivos': [], 'medidas': {}}
    salida['guardas']['final'] = final
    salida.update({'cadena': [{'filtro': fl, 'opciones': o, 'por_que': p} for fl, o, p in cadena], 'fuerza': fuerza, 'ganancia_db': round(ganancia, 2),
                   'objetivo_lufs': objetivo, 'despues': resumen_calidad(diag_d), 'diagnostico_despues': diag_d})
    n_orig = int(round(diag['duracion'] * M.SR))
    if final['peor']:
        tmp.unlink(missing_ok=True)
        salida.update({'archivo': None, 'nivel': 0, 'backend': 'sin proceso (revertido)',
                       'motivo': 'la comprobación final vio la voz peor (' + '; '.join(final['motivos'][:3]) + '): se queda la original'})
    elif abs(W.muestras - n_orig) > M.SR * 0.02:
        tmp.unlink(missing_ok=True)
        salida.update({'archivo': None, 'nivel': 0, 'backend': 'sin proceso (revertido)',
                       'motivo': f'la copia no dura lo mismo que el original ({W.muestras / M.SR:.3f} s / {n_orig / M.SR:.3f} s): se queda la original'})
    else:
        Path(destino).unlink(missing_ok=True)
        tmp.replace(destino)
        salida['archivo'] = str(destino)
        salida['canales'] = canales_salida
        salida['duracion'] = round(W.muestras / M.SR, 4)
    salida['segundos'] = round(time.time() - t0, 2)
    return salida


def _sustancial(cadena, diag):
    """¿La cadena cambia algo que se oiga? (un paso alto subsónico solo, con el nivel ya bien y sin picos, no justifica una copia)."""
    lo = diag.get('loudness') or {}
    fuera = lo.get('lufs') is not None and not (OBJETIVO_LUFS[0] - 1.0 <= lo['lufs'] <= OBJETIVO_LUFS[1] + 1.0)
    picos = lo.get('tp_db') is not None and lo['tp_db'] > TOPE_TP
    for f, o, _p in cadena:
        if f != 'highpass' or float(o.split('f=')[1].split(':')[0]) > 40.0:
            return True
    return bool(fuera or picos)


def elegir_extractos(segmentos, ruta, largo=10.0, n=6):
    """Hasta `n` extractos de `largo` s repartidos por el timeline (un video corto: entero)."""
    dur = sum(b - a for a, b in segmentos) if segmentos else float((M.info(ruta) or {}).get('duracion') or 0.0)
    if dur <= 90.0:
        return [(0.0, dur)]
    return [(round(p * dur - largo / 2, 2), round(p * dur + largo / 2, 2)) for p in np.linspace(0.1, 0.9, n)]


def resumen_calidad(d):
    """Las cifras que se enseñan antes/después."""
    if not d:
        return None
    lo = d.get('loudness') or {}
    return {'suelo_ruido_db': d.get('suelo_ruido_db'), 'snr_db': d.get('snr_db'), 'lufs': lo.get('lufs'), 'lra': lo.get('lra'), 'tp_db': lo.get('tp_db'),
            'clipping': d.get('clipping'), 'sibilancia': d.get('sibilancia'), 'sibilancia_p95_db': d.get('sibilancia_p95_db'),
            'hum': d.get('hum'), 'inteligibilidad': d.get('inteligibilidad'), 'snr_1_4k_db': d.get('snr_1_4k_db'), 'noise_score': d.get('noise_score'),
            'ruido': d.get('ruido'), 'problemas': list(d.get('problemas') or [])}
