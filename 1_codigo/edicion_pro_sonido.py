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
CARPETAS = {                        # (v5.4.52: + «Interfaz (CC0)», los packs de Kenney: más variaciones, menos repetición)
    'whoosh': ['Whoosh'],
    'pop': ['Esenciales:pop', 'Modo simple:pop', 'Click', 'Interfaz (CC0):pop_'],
    'click': ['Click', 'Esenciales:click', 'Interfaz (CC0):click_'],
    'ui': ['futurista', 'Esenciales:ui', 'Interfaz (CC0):ui_'],
    'corte': ['Shutter', 'Esenciales:camera'],
    'error': ['Power Down', 'Interfaz (CC0):error_'],
    'riser': ['Riser'],
    'hit': ['Bass Hit', 'Hit', 'Slams'],
    # v5.5.3: las escenas a pantalla completa (edicion_pro_escenas.sonidos), con la biblioteca nueva
    'pin': ['Pop:pin drop', 'Pop:deep pop'], 'papel': ['Papel'], 'camara': ['Cámara', 'Shutter'], 'teclado': ['Teclado y texto:typ', 'Teclado y texto'],
    'sello': ['Hit:pro ', 'Slams'], 'grito': ['Gritos y ovación'], 'correcto': ['Correcto'], 'tijera': ['Papel', 'Click:pro '],
}
CHOQUE_S = 0.12                     # una textura menor no suena a menos de esto de un sonido de los captions
_CACHE = {}
_USADOS = set()                     # lo que ya sonó en ESTE video: se prefiere lo que no (que no se repita), si queda


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
    out = {'dur': 1.0, 'pico': 0.1, 'ataque': 0.0, 'rms_db': -12.0}
    try:
        import av
        import numpy as np
        trozos, sr = [], 48000
        with av.open(str(ruta)) as c:
            st = c.streams.audio[0]
            sr = int(st.rate or 48000)
            for fr in c.decode(st):
                escala = {'s16': 32768.0, 's16p': 32768.0, 's32': 2147483648.0, 's32p': 2147483648.0, 'u8': 128.0, 'u8p': 128.0}.get(fr.format.name, 1.0)
                a = fr.to_ndarray().astype('float32') / escala                # a ±1 (los WAV suelen venir en enteros de 16 bits)
                trozos.append(np.abs(a).mean(axis=0) if a.ndim > 1 else np.abs(a))
        x = np.concatenate(trozos) if trozos else np.zeros(1)
        v = max(1, int(sr * 0.01))                                    # ventanas de 10 ms
        n = len(x) // v
        env = x[:n * v].reshape(n, v).mean(axis=1) if n else x
        m = float(env.max()) or 1.0
        w = max(1, int(sr * 0.1))                                     # lo más fuerte en 100 ms (≈ lo que se oye), en dBFS
        nw = len(x) // w
        rms = float(np.sqrt((x[:nw * w].reshape(nw, w) ** 2).mean(axis=1)).max()) if nw else float(np.sqrt((x ** 2).mean()))
        out = {'dur': round(len(x) / float(sr), 3), 'pico': round(float(env.argmax()) * v / sr, 3),
               'ataque': round(float(next((i for i, e in enumerate(env) if e >= 0.3 * m), 0)) * v / sr, 3),
               'rms_db': round(20 * float(np.log10(max(rms, 1e-6))), 2)}
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
    nuevos = [f for f in fs if str(f) not in _USADOS]
    fs = nuevos or fs
    if largo:
        fs = sorted(fs, key=lambda f: abs(analizar(f)['pico'] - largo))[:2]
    f = rng.choice(fs)
    _USADOS.add(str(f))
    return f, analizar(f)


def _primer_tiempo(p, i=0, defecto=0.0):
    try:
        return float(str((p.get('valores') or {}).get('tiempos') or '').split(',')[i])
    except (ValueError, IndexError):
        return defecto


# v5.4.51: los niveles de la guía (−12 whoosh, −7 textura, −5 riser) son de SU biblioteca; con archivos de volumen distinto, un nivel fijo dejaba
# efectos por encima de la voz («están altos y no concuerdan»). Ahora cada efecto se ajusta a lo fuerte que es de verdad, para quedar a estos
# dB POR DEBAJO de la voz del video (como la referencia: ningún efecto supera la voz).
BAJO_LA_VOZ = {'whoosh': 13.0, 'whoosh_grande': 11.0, 'textura': 10.0, 'riser': 9.0, 'hit': 8.0, 'corte': 12.0}
SEPARACION = {'whoosh': 0.45, 'textura': 0.3}                       # Tema 5: dos efectos de la misma familia, nunca más juntos que esto


def _nivel(familia, nivel_guia, info, voz_db):
    """dB del clip: con la voz medida, el efecto queda BAJO_LA_VOZ dB por debajo de ella (según lo fuerte que suena el archivo); sin ella, el de la guía."""
    if voz_db is None:
        return nivel_guia
    return round(max(-36.0, min(4.0, voz_db - BAJO_LA_VOZ.get(familia, 11.0) - float(info.get('rms_db', -12.0)))), 1)


def nivel_voz(video):
    """Lo fuerte que suena la voz del video (percentil 90 de ventanas de 100 ms con voz, dBFS), o None."""
    try:
        import av
        import numpy as np
        trozos, sr = [], 16000
        with av.open(str(video)) as c:
            st = c.streams.audio[0]
            rs = av.AudioResampler(format='flt', layout='mono', rate=sr)
            for fr in c.decode(st):
                for g in rs.resample(fr):
                    trozos.append(g.to_ndarray().ravel())
        x = np.concatenate(trozos)
        w = sr // 10
        n = len(x) // w
        db = 20 * np.log10(np.sqrt((x[:n * w].reshape(n, w) ** 2).mean(axis=1)) + 1e-9)
        voz = db[db > np.percentile(db, 40)]
        return round(float(np.percentile(voz, 90)), 1) if len(voz) else None
    except Exception:
        return None


def disenar(plan, fps, rng, choques=(), cortes=(), voz_db=None):
    """El plan de sonido de la PRO: (familia, instante del evento, ancla, nivel) por cada movimiento y evento de los gráficos, risers antes de las
    transiciones grandes y un clic de cámara en los cortes con punch-in. Con `voz_db` cada efecto queda bajo la voz (_nivel). El Tema 5 es más
    sobrio: separaciones mínimas, como mucho 2 risers, y la escena que sale no suena si entra otra al momento. Devuelve los eventos para colocar_pro."""
    t5 = bool(plan.get('tema5'))
    _USADOS.clear()
    ev = []                                                          # (tipo, t, nivel, largo deseado, ancla, qué)

    def mov(t, grande=False, largo=0.7, que=''):
        ev.append(('whoosh', t, NIVEL['whoosh_grande' if grande else 'whoosh'], largo, 'pico', que))

    def tex(clave, t, que='', nivel=None):
        ev.append((clave, t, NIVEL['textura'] if nivel is None else nivel, None, 'ataque', que))

    transiciones = []                                                # (t, qué) donde va un riser + hit
    for p in plan.get('piezas') or []:
        a, b, pz = float(p['ini']), float(p['fin']), p['pieza']
        if p.get('quitar'):
            continue                                                 # no se puso (no cabía sin tapar una cara): no suena
        if pz == 'orbita' and p.get('capa') == 'delante':
            continue
        if pz == 'subtitulo':                                         # Tema 5: los bloques normales ya suenan con el modo de Sonido de GO
            if (p.get('valores') or {}).get('modo') == 'detras':
                mov(a + 0.08, largo=0.5, que='la clave detrás de la persona')
            continue
        if pz == 'acomp':                                             # Tema 5: los acompañantes bajo el caption
            v = p.get('valores') or {}
            tp = v.get('tipo')
            if tp == 'lugar':
                mov(a + 0.1, largo=0.35, que='entra el lugar')
                tex('pop', a + 0.3, 'cae el pin')
            elif tp == 'redes':
                tex('click', a + 0.6, 'se pulsa el botón')
            elif tp in ('cifra', 'dinero', 'tiempo'):
                tex('ui', a + 0.15, f'entra {tp}')
            else:
                tex('pop', a + 0.12, f'entra {tp}')
            continue
        if pz == 'skill':                                             # Tema 5 (sistema de la skill): interfaz = clics y pops; escenas = whoosh
            c, v = p.get('remotion'), p.get('valores') or {}
            if c == 'PasosT5':
                if v.get('gancho'):
                    for i in range(int(v.get('n') or 3)):
                        tex('pop', a + 0.15 + i * 0.16, f'paso {i + 1} del gancho')
                else:
                    tex('click', a + 0.25, 'se marca el paso')
            elif c == 'DeslizadorT5':
                mov(a + 0.1, largo=0.4, que='entra el deslizador')
                tex('click', b - 0.55, 'el punto llega al final')
            elif c == 'EscenaT5':
                completa = v.get('mitad') != 'arriba'
                mov(a + 0.05, grande=completa, largo=0.6 if completa else 0.45, que='entra la escena de papel')
                if v.get('variante') in ('icono', 'cifra', 'tarjeta'):
                    tex('pop', a + 0.35, f"llega {v.get('variante')}")
                for o in (v.get('objetos') or [])[:4]:                   # cada objeto suena cuando aparece (cuando se nombra); 4 como mucho
                    tex('click' if o.get('tipo') in ('ficha', 'barra', 'calendario', 'lista') else 'pop', a + float(o.get('t') or 0.3) + 0.05, f"aparece {o.get('tipo')}")
                    if o.get('tipo') == 'app' and o.get('insignia'):
                        tex('ui', a + float(o.get('t_escala') or 1.0) + 0.4, 'se encoge')
                otra = any(q is not p and q.get('pieza') == 'skill' and q.get('remotion') == 'EscenaT5' and abs(float(q['ini']) - b) < 0.3
                           for q in plan.get('piezas') or [])
                if not otra:                                             # escena tras escena: solo suena la que entra
                    mov(b - 0.2, largo=0.4, que='sale la escena')
                transiciones.append((a, 'video → escena'))
            continue
        if pz == 'tarjeta':                                           # Tema 5 (v5.4.52): la tarjeta encima de la cabeza
            v = p.get('valores') or {}
            tp = v.get('tipo')
            mov(a + 0.08, largo=0.4, que=f'entra la tarjeta ({tp})')
            if tp == 'mapa':
                tex('pop', a + 1.2, 'cae el pin')
            elif tp == 'grafica':
                tex('ui', a + 0.45, 'crecen las barras')
            elif tp == 'tachado':
                tex('error', a + float(v.get('t_tachar') or 0.6) + 0.1, 'se tacha la frase')
            elif tp == 'lista':
                for x in (v.get('tiempos') or [])[:4]:
                    tex('click', a + float(x) + 0.22, 'se marca una cosa de la lista')
            continue
        if pz == 'sticker':
            tex('corte', a + 0.03, 'la imagen se congela (sticker)', NIVEL['corte'])
            continue
        if pz == 'editorial':                                        # Tema 6: el visor, la barra de búsqueda, el perfil
            v = p.get('valores') or {}
            tp = v.get('tipo')
            if tp == 'visor':
                tex('corte', a + 0.3, 'el visor enfoca la cara', NIVEL['corte'])
            elif tp == 'buscar':
                tex('ui', a + 0.3, 'aparece la barra de búsqueda')
                tex('click', a + 0.35 + 0.075 * len(str(v.get('texto') or '')) + 0.35, 'se pulsa enviar')
            else:
                mov(a + 0.08, largo=0.35, que=f'entra {tp}')
                tex('ui', a + 0.4, f'cuenta {tp}')
            continue
        if pz == 'final':
            mov(a + 0.05, grande=True, largo=0.6, que='entra la pantalla final')
            tex('click', a + min(1.25, max(0.8, (b - a) - 1.1)), 'se pulsa el botón de seguir')
            continue
        if pz == 'foco':
            tex('hit', a + 0.02, 'el fondo se apaga (foco)')
            continue
        if pz == 'fondo':
            mov(a + 0.22, grande=bool(p.get('pantalla')), largo=0.6, que='entra la escena')
            mov(b + 0.17, largo=0.4, que='sale la escena')
            transiciones.append((a, 'video → escena'))
        elif pz == 'ubicacion':                                     # mapa + bandera (Remotion): iris, vuelo de cámara, pin, bandera
            mov(a + 0.22, grande=True, largo=0.6, que='entra el mapa')
            mov(a + 0.75, largo=0.6, que='la cámara vuela al país')
            tex('pop', a + 1.1, 'cae el pin')
            tex('ui', a + 1.3, 'entra la bandera')
            transiciones.append((a, 'video → mapa'))
        elif pz == 'plantilla' and p.get('escena_mg'):              # v5.5.3: escena a pantalla completa del director (Escenas9)
            import edicion_pro_escenas as ES
            mov(a + 0.08, grande=True, largo=0.6, que=f"entra la escena {p.get('remotion')}")
            for t_rel, clave, que in ES.sonidos(p.get('remotion'), p.get('valores') or {}, b - a):
                tex(clave, a + t_rel, que)
            mov(b - 0.12, largo=0.4, que='sale la escena')
            transiciones.append((a, 'video → escena'))
        elif pz == 'plantilla':                                     # biblioteca Remotion: cada composición con su sonido
            c = p.get('remotion')
            if c == 'Sesion':
                tex('corte', a + 0.18, 'flash de la cámara', NIVEL['textura'])
            elif c in ('Tarjeta', 'Grafica', 'Encuesta', 'Comentario', 'Pasos', 'Fecha'):
                mov(a + 0.2, largo=0.4, que=f'entra {c}')
                if c == 'Comentario':
                    tex('ui', a + 0.75 + 0.11 * len(str((p.get('valores') or {}).get('palabra') or '')) + 0.35, 'comentario enviado')
                if c == 'Pasos':
                    for k in range(len(str((p.get('valores') or {}).get('pasos') or '').split(','))):
                        tex('click', a + 0.75 + k * 0.35, 'paso')
            elif c in ('Notificacion', 'Interruptor', 'Capitulos'):
                tex('ui', a + (0.7 if c == 'Interruptor' else 0.1), c)
            elif c in ('Saludo', 'Ninas', 'Pastilla'):
                tex('pop', a + (0.75 if c == 'Saludo' else 0.1), c)
            else:                                                    # Titulo, Pareja
                tex('ui', a + 0.25, 'título')
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
    zooms = [float(x) for x in plan.get('_zoom') or []]
    for t in zooms:
        mov(t, largo=0.3, que='transición con zoom')
    for t in cortes or []:
        if any(abs(float(t) - z) < 0.3 for z in zooms):
            continue                                                 # ese corte ya suena con el whoosh de su transición
        tex('corte', float(t), 'corte con punch-in', NIVEL['corte'])
    # al menos dos risers si hay transiciones; el primero, a ~5 s del gancho
    transiciones.sort()
    elegidas = []
    for t, que in transiciones:
        if t >= 2.0 and (not elegidas or t - elegidas[-1][0] >= (8.0 if t5 else 4.0)):
            elegidas.append((t, que))
    out = []
    usados_cap = sorted(float(x) for x in choques)
    for t, que in elegidas[:(2 if t5 else 6)]:
        f, info = _elegir('riser', rng, largo=2.0, hasta=t)
        if f is not None:
            out.append({'pista': PISTAS['riser'], 'ini': int(round((t - info['pico']) * fps)), 'archivo': str(f), 'dur': min(4.0, info['dur']),
                        'db': _nivel('riser', NIVEL['riser'], info, voz_db), 'que': f'riser · {que}'})
            g, ig = _elegir('hit', rng, ancla='ataque', hasta=t)
            if g is not None:
                out.append({'pista': PISTAS['hit'], 'ini': int(round(max(0.0, t - ig['ataque']) * fps)), 'archivo': str(g),
                            'dur': min(3.0, ig['dur']), 'db': _nivel('hit', NIVEL['hit'], ig, voz_db), 'que': f'hit · {que}'})
    ultimo = {'whoosh': -99.0, 'textura': -99.0}
    for clave, t, nivel, largo, ancla, que in sorted(ev, key=lambda e: e[1]):
        familia = 'whoosh' if clave == 'whoosh' else 'textura'
        if familia == 'textura' and clave != 'error' and any(abs(t - u) < CHOQUE_S for u in usados_cap):
            continue                                                 # no pisar el sonido de un caption (los captions llevan uno por palabra)
        if t5 and t - ultimo[familia] < SEPARACION[familia]:
            continue                                                 # Tema 5: nada amontonado
        f, info = _elegir(clave, rng, largo=largo, ancla=ancla, hasta=t)
        if f is None:
            continue
        ultimo[familia] = t
        ini = t - info[ancla]
        guia = 'whoosh_grande' if (clave == 'whoosh' and nivel == NIVEL['whoosh_grande']) else ('corte' if clave == 'corte' else familia)
        out.append({'pista': PISTAS[familia], 'ini': int(round(ini * fps)), 'archivo': str(f), 'dur': min(3.0, info['dur']),
                    'db': _nivel(guia, nivel, info, voz_db), 'que': que})
    return out

