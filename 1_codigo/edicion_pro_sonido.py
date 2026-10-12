# CineCaptions · By Cinema Productions
# 1_codigo/edicion_pro_sonido.py — el diseño de sonido de la «Edición PRO»: cada gráfico suena como lo haría un editor profesional.
"""
Reglas (de la guía de sonido para reels virales que nos pasó el usuario):

    · El sonido SUBRAYA el movimiento: si no pasa nada en pantalla, no suena nada.
    · Tres familias, tres trabajos, una pista cada una (PRO-WHOOSH · PRO-TEXTURA · PRO-RISER · PRO-HIT):
        WHOOSH   algo que se MUEVE (entra deslizando, iris, órbita, la ficha final)  → −12 dB (−10 los grandes); el PICO del whoosh
                 cae en el fotograma más rápido del movimiento.
        TEXTURA  algo que PASA sin deslizarse (pop de un icono, cifra, cada elemento de una lista, clic de interfaz, corte/cámara, apagón
                 del gris) → −7 dB; su ATAQUE cae justo en el fotograma del evento.
        RISER    la anticipación ANTES de una transición (gancho → cuerpo, video → escena de motion graphics) → −5 dB; TERMINA en el fotograma
                 de la transición y un HIT (−8 dB) cae debajo, en ese mismo fotograma. Al menos dos por video si hay transiciones.
    · De cada carpeta se «escucha» cada variación (`analizar`: duración, pico y ataque) y se elige la que mejor encaja con lo que dura el
      movimiento; la voz manda: nada suena por encima (los niveles ya son bajos) y las texturas menores no pisan los sonidos de los captions.

    disenar(plan, fps, rng, choques, cortes) -> [{'pista', 'ini' (fotograma desde el inicio), 'archivo', 'dur' (s), 'db', 'que'}]
"""
from __future__ import annotations

from pathlib import Path

PISTAS = {'whoosh': 'PRO-WHOOSH', 'textura': 'PRO-TEXTURA', 'riser': 'PRO-RISER', 'hit': 'PRO-HIT'}
NIVEL = {'whoosh': -12.0, 'whoosh_grande': -10.0, 'textura': -7.0, 'riser': -5.0, 'hit': -8.0, 'corte': -10.0}
CARPETAS = {
    'whoosh': ['Whoosh'],
    'pop': ['Esenciales:pop', 'Modo simple:pop', 'Click'],
    'click': ['Click', 'Esenciales:click'],
    'ui': ['futurista', 'Esenciales:ui'],
    'corte': ['Shutter', 'Esenciales:camera'],
    'error': ['Power Down'],
    'riser': ['Riser'],
    'hit': ['Bass Hit', 'Hit', 'Slams'],
}
CHOQUE_S = 0.12                     # una textura menor no suena a menos de esto de un sonido de los captions
_CACHE = {}


def _biblioteca() -> Path:
    try:
        from sfx_rules import base_recursos
        return Path(base_recursos()) / 'sfx_library'
    except Exception:
        return Path(__file__).resolve().parent.parent / '2_recursos' / 'sfx_library'


def analizar(ruta) -> dict:
    """{'dur', 'pico', 'ataque'} en segundos: dónde está lo más fuerte del sonido y dónde arranca de verdad (≥ 30 % del máximo)."""
    ruta = Path(ruta)
    k = f'{ruta}|{ruta.stat().st_mtime_ns if ruta.exists() else 0}'
    if k in _CACHE:
        return _CACHE[k]
    out = {'dur': 1.0, 'pico': 0.1, 'ataque': 0.0}
    try:
        import av
        import numpy as np
        trozos, sr = [], 48000
        with av.open(str(ruta)) as c:
            st = c.streams.audio[0]
            sr = int(st.rate or 48000)
            for fr in c.decode(st):
                a = fr.to_ndarray().astype('float32')
                trozos.append(np.abs(a).mean(axis=0) if a.ndim > 1 else np.abs(a))
        x = np.concatenate(trozos) if trozos else np.zeros(1)
        v = max(1, int(sr * 0.01))                                    # ventanas de 10 ms
        n = len(x) // v
        env = x[:n * v].reshape(n, v).mean(axis=1) if n else x
        m = float(env.max()) or 1.0
        out = {'dur': round(len(x) / float(sr), 3), 'pico': round(float(env.argmax()) * v / sr, 3),
               'ataque': round(float(next((i for i, e in enumerate(env) if e >= 0.3 * m), 0)) * v / sr, 3)}
    except Exception:
        pass
    _CACHE[k] = out
    return out


def _archivos(clave):
    lib = _biblioteca()
    out = []
    for c in CARPETAS.get(clave, []):
        carpeta, _, filtro = c.partition(':')
        d = lib / carpeta
        if d.is_dir():
            out += [f for f in sorted(d.iterdir()) if f.suffix.lower() in ('.wav', '.mp3') and (not filtro or filtro in f.name.lower())]
    return out


def _elegir(clave, rng, largo=None, ancla='pico', hasta=None):
    """La variación de esa carpeta que mejor encaja («escuchar» las variaciones): solo las que caben (su `ancla` ≤ `hasta` segundos, para que
    el sonido no empiece antes del principio) y, con `largo`, las de subida (tiempo hasta el pico) más parecida al movimiento; una al azar
    entre las dos mejores (con la semilla del video)."""
    fs = [f for f in _archivos(clave) if hasta is None or analizar(f)[ancla] <= hasta]
    if not fs:
        return None, None
    if largo:
        fs = sorted(fs, key=lambda f: abs(analizar(f)['pico'] - largo))[:2]
    f = rng.choice(fs)
    return f, analizar(f)


def _primer_tiempo(p, i=0, defecto=0.0):
    try:
        return float(str((p.get('valores') or {}).get('tiempos') or '').split(',')[i])
    except (ValueError, IndexError):
        return defecto


def disenar(plan, fps, rng, choques=(), cortes=()):
    """El plan de sonido de la PRO: (familia, instante del evento, ancla, nivel) por cada movimiento y evento de los gráficos, risers antes de las
    transiciones grandes y un clic de cámara en los cortes con punch-in. Devuelve los eventos listos para colocar_pro."""
    ev = []                                                          # (tipo, t, nivel, largo deseado, ancla, qué)

    def mov(t, grande=False, largo=0.7, que=''):
        ev.append(('whoosh', t, NIVEL['whoosh_grande' if grande else 'whoosh'], largo, 'pico', que))

    def tex(clave, t, que='', nivel=None):
        ev.append((clave, t, NIVEL['textura'] if nivel is None else nivel, None, 'ataque', que))

    transiciones = []                                                # (t, qué) donde va un riser + hit
    for p in plan.get('piezas') or []:
        a, b, pz = float(p['ini']), float(p['fin']), p['pieza']
        if pz == 'orbita' and p.get('capa') == 'delante':
            continue
        if pz == 'fondo':
            mov(a + 0.22, grande=bool(p.get('pantalla')), largo=0.6, que='entra la escena')
            mov(b + 0.17, largo=0.4, que='sale la escena')
            transiciones.append((a, 'video → escena'))
        elif pz == 'icono':
            tex('pop', a + 0.35, 'aparece el icono')
        elif pz == 'cifra':
            tex('click', a + _primer_tiempo(p), 'la cifra')
        elif pz == 'lista':
            ts = str((p.get('valores') or {}).get('tiempos') or '').split(',')
            for x in ts[1:5]:
                try:
                    tex('click', a + float(x), 'elemento de la lista')
                except ValueError:
                    pass
        elif pz == 'orbita':
            mov(a + 0.35, largo=0.35, que='los iconos salen a girar')
            transiciones.append((b, 'gancho → cuerpo'))
        elif pz == 'cta':
            mov(a + 0.3, largo=0.4, que='entra la ficha final')
            tex('ui', a + _primer_tiempo(p, 5, 1.35), 'el botón')
        elif pz == 'etiqueta':
            tex('ui', a + max(0.12, _primer_tiempo(p)), 'etiqueta')
        elif pz == 'marco':
            tex('click', a, 'marco')
        elif pz == 'nombres':
            transiciones.append((a + 0.5, 'los nombres'))
        elif pz in ('titular', 'rotulo'):
            mov(a + _primer_tiempo(p) + 0.1, largo=0.6, que=pz)
    for c in plan.get('_iconos3d') or []:
        tex('pop', float(c['ini']) + 0.2, 'icono 3D')
    for a, _b in plan.get('gris') or []:
        tex('error', float(a), 'modo error (gris)')
    for m in plan.get('_broll_puesto') or []:
        tex('corte', float(m['ini']), 'entra el B-roll', NIVEL['corte'])
        transiciones.append((float(m['ini']), 'video → B-roll'))
    for t in cortes or []:
        tex('corte', float(t), 'corte con punch-in', NIVEL['corte'])
    # al menos dos risers si hay transiciones; el primero, a ~5 s del gancho
    transiciones.sort()
    elegidas = []
    for t, que in transiciones:
        if t >= 2.0 and (not elegidas or t - elegidas[-1][0] >= 4.0):
            elegidas.append((t, que))
    out = []
    usados_cap = sorted(float(x) for x in choques)
    for t, que in elegidas[:6]:
        f, info = _elegir('riser', rng, largo=2.0, hasta=t)
        if f is not None:
            out.append({'pista': PISTAS['riser'], 'ini': int(round((t - info['pico']) * fps)), 'archivo': str(f), 'dur': min(4.0, info['dur']),
                        'db': NIVEL['riser'], 'que': f'riser · {que}'})
            g, ig = _elegir('hit', rng, ancla='ataque', hasta=t)
            if g is not None:
                out.append({'pista': PISTAS['hit'], 'ini': int(round(max(0.0, t - ig['ataque']) * fps)), 'archivo': str(g),
                            'dur': min(3.0, ig['dur']), 'db': NIVEL['hit'], 'que': f'hit · {que}'})
    for clave, t, nivel, largo, ancla, que in sorted(ev, key=lambda e: e[1]):
        familia = 'whoosh' if clave == 'whoosh' else 'textura'
        if familia == 'textura' and clave != 'error' and any(abs(t - u) < CHOQUE_S for u in usados_cap):
            continue                                                 # no pisar el sonido de un caption (los captions llevan uno por palabra)
        f, info = _elegir(clave, rng, largo=largo, ancla=ancla, hasta=t)
        if f is None:
            continue
        ini = t - info[ancla]
        out.append({'pista': PISTAS[familia], 'ini': int(round(ini * fps)), 'archivo': str(f), 'dur': min(3.0, info['dur']), 'db': nivel,
                    'que': que})
    return out

