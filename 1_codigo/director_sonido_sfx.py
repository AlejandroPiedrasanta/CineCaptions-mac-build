# CineCaptions · By Cinema Productions
# 1_codigo/director_sonido_sfx.py — «AI Sound Director», FASE 3: cada sonido del diseño hecho a la medida, en su WAV y listo para su pista AI.
"""
fabricar(diseno, carpeta, nivel_voz_db, modo='hibrido') → {'eventos': [eventos 'sonido' con 'pista' para el plan de Efectos], 'puestos', 'segundos'}

MODO (elegido por el usuario al comparar las 4 demos del Tema 1, 2026-10-21): 'hibrido' = para golpes, whooshes, risers, acentos y tics, el mejor
archivo de la biblioteca curada que pase el Quality Gate y el ajuste semántico (director_sonido_fuentes) + una capa procedural ajustada a ESE motion
(sub y clic bajo el golpe, aire que sigue el easing y la dirección bajo el whoosh); si ningún archivo pasa, procedural a la medida
(director_sonido_sintesis). 'procedural' = solo síntesis. Nunca la biblioteca legacy de la app (DISABLED_FOR_NEW_DESIGN).

Cada sonido: alineado a su ANCLA (el pico del golpe cae en el fotograma que manda; el riser acaba 30 ms antes), con su nivel RELATIVO a la voz
horneado dentro del archivo (Resolve ignora el volumen de clip por script), WAV 48 kHz 24 bits con nombre por contenido (el mismo diseño = el mismo
archivo: re-aplicar no rehace nada) en ~/DaVinciSubtitles/sound_director/<huella>/sfx/.
"""
import hashlib
import json
import time
from pathlib import Path

import numpy as np

SR = 48000
MODO = 'hibrido'
VERSION = 2                                     # súbela si cambia la síntesis o la mezcla de capas: los WAV viejos no se reutilizan (2: golpe por su pico final)
CATEGORIA = {'golpe': 'golpe', 'whoosh': 'whoosh', 'giro': 'whoosh', 'riser': 'riser', 'trazo': 'trazo', 'acento': 'tonal', 'tick': 'ui', 'pop': 'ui'}
_CANDIDATOS = {}


def _ganancia(x, objetivo_db):
    import director_sonido_sintesis as S
    return x * (10 ** ((objetivo_db - S.rms_activo_db(x)) / 20.0))


def _pico_idx(x):
    m = np.abs(x).max(axis=0)
    env = np.convolve(m, np.ones(96) / 96, 'same')
    return int(np.argmax(env))


def _balance(x, pos):
    if not pos:
        return x
    a = (np.clip(pos, -1, 1) + 1) * np.pi / 4
    return np.vstack((x[0] * np.cos(a) * 1.414, x[1] * np.sin(a) * 1.414)).astype(np.float32)


def sintetizar(e, rng):
    """El sonido procedural de un evento: (audio (2, n), segundos desde el inicio del archivo hasta el ancla)."""
    import director_sonido_sintesis as S
    p, t = e['params'], e['tipo']
    if t == 'golpe':
        return S.golpe(p.get('peso', 0.7), p.get('brillo', 0.5), p.get('cola', 0.4), p.get('pre', 0.09), rng), p.get('pre', 0.0)
    if t == 'whoosh':
        x = S.whoosh(max(0.12, e['dur'] - 0.12), p.get('direccion', 0.0), p.get('easing', 'easeInOutCubic'), p.get('brillo', 0.5), p.get('peso', 0.4), rng)
        return x, e['ancla'] - e['t']
    if t == 'giro':
        return S.giro(max(0.1, e['dur'] - 0.05), p.get('brillo', 0.5), rng), e['ancla'] - e['t']
    if t == 'trazo':
        return S.trazo(max(0.1, e['dur'] - 0.05), p.get('potencia', 2.4), p.get('brillo', 0.5), rng), 0.0
    if t == 'riser':
        return S.riser(e['dur'], p.get('brillo', 0.5), rng=rng), e['dur']
    if t == 'acento':
        return S.acento(p.get('nota', 523.25), e['dur'], p.get('brillo', 0.5)), 0.0
    if t == 'tick':
        return S.tick(p.get('brillo', 0.5), rng), 0.0
    if t == 'pop':
        return S.pop(p.get('brillo', 0.5), rng), 0.0
    return None, 0.0


def _candidatos(tipo):
    import director_sonido_fuentes as F
    if tipo not in _CANDIDATOS:
        _CANDIDATOS[tipo] = F.candidatos(tipo)
    return _CANDIDATOS[tipo]


def de_biblioteca(e, usados):
    """El mejor archivo de la biblioteca curada que pasa el Quality Gate y el ajuste semántico, recortado y alineado. (audio, offset, elección).
    `params['evitar']` = archivos que el usuario ya no quiere para ESTE evento («otro SFX» / «otra textura»)."""
    import director_sonido_fuentes as F
    tipo = CATEGORIA.get(e['tipo'])
    evitar = {str(x) for x in (e['params'].get('evitar') or [])}
    cands = [c for c in _candidatos(tipo) if str(c) not in evitar]
    if not cands:
        return None, 0.0, {'candidatos': 0}
    objetivo = {'tipo': tipo, 'dur': e['dur'], 'brillo': e['params'].get('brillo', 0.5), 'energia': 0.8 if e['tipo'] == 'golpe' else 0.4}
    ruta, ranking = F.elegir(cands, objetivo, usados)
    eleccion = {'candidatos': len(ranking), 'rechazados_quality_gate': sum(1 for r in ranking if r[0] < 0), 'elegido': Path(ruta).name if ruta else None,
                'top3': [(r[0], Path(r[1]).name) for r in ranking[:3]]}
    if not ruta:
        return None, 0.0, eleccion
    usados[ruta] = usados.get(ruta, 0) + 1
    largo = e['dur'] + (0.6 if e['tipo'] in ('golpe', 'acento') else 0.2)
    x = F.leer_para_mezcla(ruta, None if e['tipo'] == 'riser' else largo, 0.25 if e['tipo'] in ('golpe', 'acento') else 0.04)
    if x is None:
        return None, 0.0, eleccion
    eleccion['archivo'] = str(ruta)
    if e['tipo'] == 'riser':
        x = x[:, -int(e['dur'] * SR):] if x.shape[1] > e['dur'] * SR else x
        return x, x.shape[1] / SR, eleccion
    return _balance(x, e['params'].get('direccion', 0.0)), _pico_idx(x) / SR, eleccion


def _capa(e, rng):
    """La capa procedural del modo híbrido, a la medida de ESE motion: (audio, segundos desde el inicio hasta el ancla, dB bajo el archivo) o None."""
    import director_sonido_sintesis as S
    p = e['params']
    if e['tipo'] == 'golpe':
        return S.golpe(p.get('peso', 0.7), p.get('brillo', 0.5), 0.15, 0.0, rng), 0.0, 6.0
    if e['tipo'] == 'whoosh':
        return S.whoosh(max(0.12, e['dur'] - 0.12), p.get('direccion', 0.0), p.get('easing', 'easeInOutCubic'), 0.8, 0.2, rng), e['ancla'] - e['t'], 8.0
    return None


def _menos_graves(x, corte_hz=180.0):
    """Paso alto suave (por FFT, rampa de una octava): «menos graves»."""
    n = x.shape[1]
    X = np.fft.rfft(x, axis=1)
    f = np.fft.rfftfreq(n, 1.0 / SR)
    g = np.clip(np.log2(np.maximum(f, 1.0) / (corte_hz / 2.0)), 0.0, 1.0)
    return np.fft.irfft(X * g, n, axis=1).astype(np.float32)


def _transitorio_suave(x, off, ms=22.0):
    """El ataque en el ancla, redondeado (de 0,45 a 1 en `ms`): «menos transitorio»."""
    i0 = max(0, int(round(off * SR)) - int(0.002 * SR))
    k = int(ms / 1000.0 * SR)
    y = x.copy()
    y[:, :i0] *= 0.45
    y[:, i0:i0 + k] *= np.linspace(0.45, 1.0, min(k, max(0, y.shape[1] - i0)))
    return y


def _variar(x, off, rng, tono=0.03, nivel_db=0.7):
    """Microvariación de un archivo que ya sonó en este video (tono ±3 %, nivel ±0,7 dB): dos toques seguidos nunca son el mismo clon. El ancla se
    corre con el cambio de tono. (El MOTIVO tonal no pasa por aquí: se repite igual a propósito.)"""
    f = 1.0 + float(rng.uniform(-tono, tono))
    n = x.shape[1]
    m = max(8, int(round(n / f)))
    pos = np.linspace(0, n - 1, m)
    y = np.vstack([np.interp(pos, np.arange(n), c) for c in x]).astype(np.float32)
    return y * (10 ** (float(rng.uniform(-nivel_db, nivel_db)) / 20.0)), off / f


def _sumar(a, off_a, b, off_b):
    """Dos sonidos alineados por su ancla en uno solo: (audio, offset)."""
    off = max(off_a, off_b)
    ia, ib = int(round((off - off_a) * SR)), int(round((off - off_b) * SR))
    n = max(ia + a.shape[1], ib + b.shape[1])
    y = np.zeros((2, n), np.float32)
    y[:, ia:ia + a.shape[1]] += a
    y[:, ib:ib + b.shape[1]] += b
    return y, off


def _nombre(e, nivel_db, modo):
    p = {k: v for k, v in e['params'].items() if not (e['tipo'] == 'acento' and k == 'semilla')}    # el motivo: la misma nota = el mismo archivo
    clave = json.dumps({'v': VERSION, 'modo': modo, 'tipo': e['tipo'], 'dur': e['dur'], 'ancla_rel': round(e['ancla'] - e['t'], 3), 'p': p,
                        'nivel': round(nivel_db, 1)}, sort_keys=True, default=str)
    return f"{e['id'].split('-')[0]}_{hashlib.sha1(clave.encode('utf-8')).hexdigest()[:12]}.wav"


def _escribir(destino, x):
    import director_sonido_medir as M
    tmp = destino.with_suffix('.tmp.wav')
    w = M.EscritorWav(tmp, 2)
    try:
        w.escribir(x)
    finally:
        w.cerrar()
    tmp.replace(destino)


def fabricar(diseno, carpeta, nivel_voz_db, modo=MODO):
    """Los sonidos del diseño (solo los GENERATE) hechos y escritos. Devuelve {'eventos', 'puestos', 'segundos'} (ver el docstring del módulo)."""
    t0 = time.time()
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    usados, salida, puestos = {}, [], []
    for e in sorted(diseno.get('eventos') or [], key=lambda e: e['t']):
        if e.get('decision') != 'GENERATE':
            continue
        fijo = e.get('plan_fijo') or {}
        if e.get('bloqueado') and fijo.get('archivo') and Path(str(fijo['archivo'])).is_file():      # BLOQUEADO: el mismo archivo y el mismo sitio
            salida.append(dict(fijo, ai=dict(fijo.get('ai') or {}, id=e['id'], tipo=e['tipo'], origen=e.get('origen'))))
            puestos.append({'id': e['id'], 'tipo': e['tipo'], 'origen': e.get('origen'), 'decision': e['decision'], 'por_que': e['por_que'],
                            'importancia': e['importancia'], 'fuente': (fijo.get('ai') or {}).get('fuente') or 'bloqueado', 'bloqueado': True,
                            'clave': e.get('clave')})
            continue
        p = e['params']
        rng = np.random.default_rng(int(p.get('semilla') or 0))
        objetivo = float(nivel_voz_db) + float(e['nivel_rel_voz_db']) + float(p.get('nivel_extra_db') or 0.0)
        x, off, fuente, eleccion = None, 0.0, 'procedural', None
        if modo == 'hibrido' and not p.get('solo_procedural'):
            x, off, eleccion = de_biblioteca(e, usados)
            if x is not None:
                fuente = 'biblioteca curada'
        if x is None:
            x, off = sintetizar(e, rng)
            fuente = ('procedural' if modo == 'procedural' or p.get('solo_procedural') or not (eleccion or {}).get('candidatos')
                      else 'procedural (ningún archivo pasó el Quality Gate)')
        if x is None or not x.size:
            puestos.append({'id': e['id'], 'tipo': e['tipo'], 'fuente': 'LEAVE_SILENT', 'por_que': 'no se pudo hacer: mejor silencio'})
            continue
        x = _ganancia(np.asarray(x, np.float32), objetivo)
        if fuente == 'biblioteca curada' and e['tipo'] != 'acento' and usados.get((eleccion or {}).get('archivo'), 0) > 1:
            x, off = _variar(x, off, rng)
        if (fuente == 'biblioteca curada' and not p.get('sin_capa')) or p.get('otra_capa'):
            capa = _capa(e, rng)
            if capa is not None:
                y, off_y, menos_db = capa
                x, off = _sumar(x, off, _ganancia(y, objetivo - menos_db), off_y)
                fuente += ' + capa procedural'
        if p.get('clic'):                                             # «mejor transitorio»: un clic nítido justo en el ancla
            import director_sonido_sintesis as S
            x, off = _sumar(x, off, _ganancia(S.tick(0.85, rng), objetivo - 6.0), 0.0)
            fuente += ' + clic'
        if p.get('graves_menos'):
            x = _menos_graves(x)
        if p.get('transitorio_menos'):
            x = _transitorio_suave(x, off)
        if e['tipo'] == 'golpe':                                      # el golpe se sincroniza por su PICO: el del sonido FINAL (archivo + capas),
            off = _pico_idx(x) / SR                                   # no el del archivo solo (una cola más fuerte lo corría +80 ms)
        pico = float(np.abs(x).max()) if x.size else 0.0
        if pico > 0.89:                                               # −1 dBFS de muestra como mucho (los true peaks los mira la fase 5)
            x = x * (0.89 / pico)
        inicio = e['ancla'] - off - (0.03 if e['tipo'] == 'riser' else 0.0)
        if inicio < 0:
            x, inicio = x[:, int(round(-inicio * SR)):], 0.0
            k = min(x.shape[1], 144)
            x[:, :k] *= np.linspace(0, 1, k)
        if x.shape[1] < 96:
            continue
        destino = carpeta / _nombre(e, objetivo, modo)
        if not destino.is_file():
            _escribir(destino, x)
        info = {'id': e['id'], 'tipo': e['tipo'], 'origen': e.get('origen'), 'decision': e['decision'], 'por_que': e['por_que'],
                'importancia': e['importancia'], 'fuente': fuente, 'nivel_db': round(objetivo, 1), 'clave': e.get('clave'), 'archivo': str(destino)}
        if eleccion and eleccion.get('elegido'):
            info['eleccion'] = eleccion
        salida.append({'tipo': 'sonido', 'pista': e['pista'], 'ini': round(inicio, 3), 'dur': round(x.shape[1] / SR, 3), 'archivo': str(destino),
                       'asset': f"{e['id']} · {fuente}", 'ai': {k: info[k] for k in ('id', 'tipo', 'origen', 'fuente', 'clave')}})
        puestos.append(info)
    try:
        import director_sonido_fuentes as F
        F.guardar_cache()
    except Exception:
        pass
    return {'eventos': salida, 'puestos': puestos, 'segundos': round(time.time() - t0, 2), 'modo': modo}
