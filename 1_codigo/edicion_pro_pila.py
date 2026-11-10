# CineCaptions · By Cinema Productions
# 1_codigo/edicion_pro_pila.py — v5.82: los motions de la referencia del Estilo 4 («Pila lima») en la Edición PRO, con «Kit de motions».
"""
El usuario (con la referencia del Estilo 4 nuevo): «los motions que salen déjalos para la Edición PRO». Se midieron en la referencia y se aprobaron
en su previa; los dibuja remotion/src/MotionsPila.tsx. Aquí se decide CUÁNDO y DÓNDE va cada uno, con los captions que GO acaba de colocar
(ya movidos por la regla de la cara: `mover`), las caras y los cortes del video. Como mucho uno de cada por video:

    piezas(plan, W, H, mover, tramos, caras_en, duracion=None) -> piezas del plan (Remotion, capa «iconos» o «delante»)

  avion      AvionPapel   el primer bloque (en el primer 40 % del video) con una línea DEBAJO de la grande y sitio a su izquierda dentro de la
                          zona segura: arranca con la grande y se posa a la izquierda de esa línea (82 px de su tinta, en el tercio bajo de su
                          letra; si tocaría una letra, baja hasta librarla). Su tamaño va con la grande (en la referencia, 174,6 px)
  tachado    TachadoRojo  la grande que se dice tras una NEGACIÓN o que nombra algo malo («no tienes TIEMPO», «el ERROR»): la línea roja la
                          cruza al decirse (recortada a la zona segura)
  rec        VisorRec     cuando se habla de grabar o de la cámara: las esquinas de cámara y «● REC» en el borde de la zona segura (2,5-6 s)
  aro        AroCara      una cara grande y sola en un bloque que habla de alguien («yo», «te», «you»…): el aro de luz y, justo cuando
                          empieza la frase siguiente, su mini píldora con sus primeras palabras
  persianas  Persianas    el corte de plano más cercano a la mitad del video, sin otro motion en pantalla
Solo con los estilos de elementos sueltos (la familia VIRAL: los Estilos 3, 4, 5, 7, 8 y 9 traen la posición y el tamaño de cada palabra).
El zoom con desenfoque de la entrada de la referencia no está aquí: toca el VIDEO, no es una capa encima.
"""
import json
import re
import unicodedata
from pathlib import Path

IDS = {'AvionPapel': 'kit:avion', 'VisorRec': 'kit:rec', 'TachadoRojo': 'kit:tachado', 'AroCara': 'kit:aro', 'Persianas': 'kit:persianas'}
NOMBRES = {'kit:avion': 'Avión de papel', 'kit:rec': 'Visor REC', 'kit:tachado': 'Tachado rojo', 'kit:aro': 'Aro de luz en la cara',
           'kit:persianas': 'Persianas en el corte', 'kit:zoom': 'Zoom con desenfoque de entrada'}
ZOOM_DUR, ZOOM_DESENFOQUE = 0.35, 16.0      # la entrada de la referencia (motions4.zoom_desenfoque + desenfoque): s y px de un vertical de 1080
# la miniatura del carrusel (herramientas_dev/hacer_previas_motions.py: el fotograma del 62 % de esta duración): ya posado, con la luz del REC
# encendida, la línea entera, el aro con su píldora y las persianas blancas
DUR_PREVIA = {'kit:avion': 2.0, 'kit:rec': 2.4, 'kit:tachado': 1.0, 'kit:aro': 2.0, 'kit:persianas': 3.0}
PROPS_PREVIA = {'kit:avion': {'x': 30, 'y': 60, 'esc': 1.1}, 'kit:rec': {'x0': 9, 'y0': 7, 'x1': 91, 'y1': 93},
                'kit:tachado': {'x0': 16, 'yc': 46, 'x1': 84, 'yb': 53, 'entra': 0.05, 'muestra': 'Miedo'},
                'kit:aro': {'cx': 50, 'cy': 46, 'r': 30, 'texto': 'Te esperamos', 'lado': 'izq'}, 'kit:persianas': {'corte': 1.88}}

AVION_DX, AVION_S_REF = -81.98, 174.6      # px (vertical de 1080): de la tinta de la línea de abajo al centro del avión · la grande de la referencia
AVION_GEO = (57.5, 14.15, 36.75, 5.375, 5.0)  # px de 720: punta, alas, semienvergadura, trazo y radio del halo (= MotionsPila.GEO)
AVION_VUELO = 1.067                         # s del primer asomo a posarse (= MotionsPila.VUELO_AVION_S)
CAPAS = ('iconos', 'delante')               # donde puede ir cada uno (la primera libre: el vigilante quita dos a la vez en la misma pista)
NO_ESTORBAN = {'acomp', 'velo', 'velo_caption', 'emoji', 'subtitulo', 'foco'}

NEGACION = {'no', 'not', 'nunca', 'never', 'sin', 'without', 'ni', 'nor', 'jamas', 'nao', 'nem', 'dont', 'doesnt', 'didnt', 'isnt', 'arent',
            'wasnt', 'cant', 'wont', 'tampoco', 'nada', 'nadie', 'ningun', 'ninguna', 'deja', 'dejes', 'stop', 'evita', 'avoid'}
# (sin «para»: casi siempre es la preposición, «para ti»)
MALO = {'error', 'errores', 'mal', 'malo', 'mala', 'malos', 'problema', 'problemas', 'miedo', 'estres', 'fallo', 'fallos', 'mentira', 'mentiras',
        'perder', 'pierdes', 'perdida', 'caro', 'cara', 'dificil', 'imposible', 'peor', 'mistake', 'mistakes', 'wrong', 'bad', 'problem', 'problems',
        'fear', 'stress', 'stresses', 'fail', 'failure', 'lie', 'lies', 'lose', 'worse', 'worst', 'hard', 'erro', 'erros', 'medo', 'ruim', 'pior'}
GRABAR = {'grabar', 'graba', 'grabo', 'grabas', 'grabamos', 'grabando', 'grabacion', 'grabaciones', 'grabe', 'camara', 'camaras', 'record',
          'records', 'recording', 'recorded', 'camera', 'cameras', 'gravar', 'gravando', 'gravacao', 'grava', 'filmar', 'filmando', 'filma',
          'filming', 'film', 'rec', 'live', 'directo', 'vlog'}
EN_VIVO = (('en', 'vivo'), ('ao', 'vivo'), ('on', 'camera'), ('en', 'directo'))
PERSONA = {'yo', 'me', 'mi', 'mis', 'conmigo', 'tu', 'te', 'ti', 'tus', 'contigo', 'usted', 'ustedes', 'i', 'my', 'myself', 'you', 'your',
           'yourself', 'eu', 'meu', 'minha', 'comigo', 'voce', 'seu', 'sua'}


def plegar(t):
    t = unicodedata.normalize('NFD', str(t).lower())
    return re.sub(r'[^a-z0-9%$]', '', ''.join(c for c in t if unicodedata.category(c) != 'Mn'))


# ------------------------------------------------------------------------------------------------ los captions de GO
def _cues():
    """Los bloques de la familia VIRAL que GO acaba de colocar (el .kinetic.json del manifiesto, idioma base) con sus elementos sueltos."""
    try:
        import edicion_pro
        m = json.loads(Path(edicion_pro.MANIFIESTO).read_text(encoding='utf-8'))
    except Exception:
        return []
    pistas = [t for t in m.get('tracks') or [] if t.get('style') == 'kinetic' and t.get('data_path')]
    if not pistas:
        return []
    try:
        cues = json.loads(Path(pistas[0]['data_path']).read_text(encoding='utf-8')).get('cues') or []
    except Exception:
        return []
    return [c for c in cues if any(str(r.get('k') or '').startswith('v ') for r in c.get('runs') or [])]


def _caja(run, W, H, dy=0.0):
    """La tinta de una palabra en px del cuadro: x0/x1 (de su avance), top/base/bajo (de su letra) y su em. None si no es de la familia VIRAL."""
    import pila_planificador as PI
    import viral_captions as VC
    from ambar_planificador import centro
    v = VC.CLIPS.get(str(run.get('k') or ''))
    if not v or not isinstance(run.get('size'), (int, float)) or not isinstance(run.get('x'), (int, float)) or not isinstance(run.get('y'), (int, float)):
        return None
    par, esp = v[0], float(v[1])
    em = float(run['size']) * PI.K_PX * W / 1080.0
    txt = str(run.get('texto') or '').strip()
    if not txt or em <= 1:
        return None
    ancho = PI.avance(txt, par, em, esp)
    xc = float(run['x']) * W
    base = float(run['y']) * H + centro(par) * em - dy
    f = PI._fuente(par, em)
    bx0, by0, _bx1, by1 = f.getbbox(txt, anchor='ls')
    cap = -f.getbbox('H', anchor='ls')[1]
    return {'x0': xc - ancho / 2.0 + bx0, 'x1': xc + ancho / 2.0, 'top': base + by0, 'cap': base - cap, 'base': base, 'bajo': base + by1,
            'em': em, 't': float(run.get('t') or 0.0), 'texto': txt, 'grande': bool(run.get('principal'))}


_FPS = [30.0]                               # (los fotogramas de `mover`: los del timeline; lo pone piezas())


def _subida(cue, mover, fps=None):
    """Lo que la regla de la cara movió ese bloque (px, + arriba)."""
    fps = float(fps or _FPS[0])
    for m in mover or []:
        try:
            if abs(float(m['ini']) / fps - float(cue['start'])) < 0.08:
                return float(m.get('subir') or 0.0)
        except (TypeError, ValueError, KeyError):
            continue
    return 0.0


def _detras(cue, tramos):
    """¿Ese bloque va detrás de la persona («Captions detrás de ti»)? Entonces nada se le pone delante."""
    a, z = float(cue['start']), float(cue['end'])
    return any(a < float(t.get('fin', 0)) and float(t.get('ini', 0)) < z for t in tramos or [])


# ------------------------------------------------------------------------------------------------ dónde cabe
def _zona(W, H):
    import zona_segura as ZS
    x0, x1 = ZS.limites_x(W, H, defecto=(0.055, 0.945))
    y0, y1 = ZS.limites_y(W, H, (0.045, 0.955))
    return x0, y0, x1, y1


def _capa_libre(piezas, ini, fin, extra_iconos=()):
    """La primera pista libre en ese rato (todo lo que haya en ella cuenta, también la píldora: el vigilante quita dos a la vez en una pista)."""
    for capa in CAPAS:
        ocupada = any(not p.get('quitar') and p.get('capa') == capa and float(p['ini']) < fin and ini < float(p['fin']) for p in piezas)
        ocupada = ocupada or (capa == 'iconos' and any(a < fin and ini < b for a, b in extra_iconos))
        if not ocupada:
            return capa
    return None


def _estorba(piezas, ini, fin):
    """¿Hay un motion de verdad (no la píldora, el velo ni un emoji) en pantalla en ese rato?"""
    return any(not p.get('quitar') and p.get('pieza') not in NO_ESTORBAN and float(p['ini']) < fin and ini < float(p['fin']) for p in piezas)


# ------------------------------------------------------------------------------------------------ avión de papel
def _caja_avion(cx, cy, F, esc):
    """La caja del avión ya posado (px) sin el halo y con él."""
    import math
    A, B, C, w, rg = AVION_GEO
    s = F * esc
    ix = -(A - 2 * B) / 3
    th = math.radians(-46.0)
    pts = [(cx + s * (x * math.cos(th) - y * math.sin(th)), cy + s * (x * math.sin(th) + y * math.cos(th)))
           for x, y in ((ix + A, 0.0), (ix - B, -C * 0.99), (ix, 0.0), (ix - B, C * 0.99))]
    m = w * s / 2.0
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    sin_halo = (min(xs) - m, min(ys) - m, max(xs) + m, max(ys) + m)
    h = rg * s * 2.0
    return sin_halo, (sin_halo[0] - h, sin_halo[1] - h, sin_halo[2] + h, sin_halo[3] + h)


def _avion(cues, W, H, mover, tramos, piezas, duracion, extra_iconos):
    U = min(W, H * 9.0 / 16.0) / 1080.0
    F = U * 1080.0 / 720.0
    zx0, zy0, zx1, zy1 = _zona(W, H)
    for cue in cues:
        if float(cue['start']) > 0.4 * duracion or _detras(cue, tramos):
            continue
        dy = _subida(cue, mover)
        cajas = [c for c in (_caja(r, W, H, dy) for r in cue.get('runs') or []) if c]
        grandes = [c for c in cajas if c['grande']]
        if not grandes:
            continue
        base_g, em_g = max(c['base'] for c in grandes), max(c['em'] for c in grandes)
        abajo = sorted((c for c in cajas if not c['grande'] and c['base'] > base_g + 0.2 * em_g), key=lambda c: c['x0'])
        if not abajo:
            continue
        b = abajo[0]
        esc = max(0.85, min(1.10, em_g / (AVION_S_REF * U)))
        sx, sy = b['x0'] + AVION_DX * U * esc, b['base'] - 0.18 * b['em']
        holgura = 7.0 * U
        for paso in range(41):                                   # si tocaría una letra (la «p» que cuelga de la grande), baja hasta librarla
            y = sy + 3.0 * U * paso
            caja, halo = _caja_avion(sx, y, F, esc)
            toca = any(caja[0] < c['x1'] + holgura and c['x0'] - holgura < caja[2] and caja[1] < c['bajo'] + holgura and c['top'] - holgura < caja[3]
                       for c in cajas)
            if not toca:
                break
        else:
            continue
        if halo[0] < (zx0 - 0.02) * W or halo[3] > (zy1 + 0.01) * H or halo[2] > zx1 * W:
            continue                                             # sin sitio dentro de la zona segura (el halo puede asomar un poco, como las letras)
        ini = max(float(cue['start']), min(c['t'] for c in grandes) - 0.02)
        fin = float(cue['end'])
        if fin - ini < AVION_VUELO + 0.35 or _estorba(piezas, ini, fin):
            continue
        capa = _capa_libre(piezas, ini, fin, extra_iconos)
        if not capa:
            continue
        return {'pieza': 'avion', 'remotion': 'AvionPapel', 'capa': capa, 'ini': round(ini, 3), 'fin': round(fin, 3),
                'motivo': f"avión de papel junto a «{' '.join(c['texto'] for c in abajo)}»",
                'valores': {'x': round(100.0 * sx / W, 3), 'y': round(100.0 * y / H, 3), 'esc': round(esc, 3), 'color': '#E0FB58'}}
    return None


# ------------------------------------------------------------------------------------------------ tachado rojo
def _tachado(cues, W, H, mover, tramos, piezas, extra_iconos):
    zx0, _zy0, zx1, _zy1 = _zona(W, H)
    previas = []
    for cue in cues:
        runs = sorted(cue.get('runs') or [], key=lambda r: float(r.get('t') or 0))
        planas = [plegar(r.get('texto') or '') for r in runs]
        contexto = previas[-3:]
        previas += planas
        if _detras(cue, tramos):
            continue
        dy = _subida(cue, mover)
        grandes = [c for c in (_caja(r, W, H, dy) for r in runs if r.get('principal')) if c]
        if not grandes:
            continue
        k = next(i for i, r in enumerate(runs) if r.get('principal'))
        antes = contexto + planas[:k]
        clave = [plegar(c['texto']) for c in grandes]
        if not (any(p in NEGACION for p in antes[-3:]) or any(p in MALO for p in clave)):
            continue
        ini, fin = min(c['t'] for c in grandes), float(cue['end'])
        if fin - ini < 0.6:
            continue
        capa = _capa_libre(piezas, ini, fin, extra_iconos)
        if not capa:
            continue
        x0, x1 = min(c['x0'] for c in grandes), max(c['x1'] for c in grandes)
        yc, yb = min(c['cap'] for c in grandes), max(c['base'] for c in grandes)
        return {'pieza': 'tachado', 'remotion': 'TachadoRojo', 'capa': capa, 'ini': round(ini, 3), 'fin': round(fin, 3),
                'motivo': f"tachado rojo sobre «{' '.join(c['texto'] for c in grandes)}»",
                'valores': {'x0': round(100 * x0 / W, 3), 'yc': round(100 * yc / H, 3), 'x1': round(100 * x1 / W, 3), 'yb': round(100 * yb / H, 3),
                            'entra': 0.12, 'lim0': round(100 * zx0, 2), 'lim1': round(100 * zx1, 2), 'color': '#E21C2E'}}
    return None


# ------------------------------------------------------------------------------------------------ visor REC
def _rec(cues, W, H, piezas, cortes, duracion):
    zx0, zy0, zx1, zy1 = _zona(W, H)
    for cue in cues:
        planas = [plegar(r.get('texto') or '') for r in sorted(cue.get('runs') or [], key=lambda r: float(r.get('t') or 0))]
        pares = list(zip(planas, planas[1:]))
        if not (any(p in GRABAR for p in planas) or any(par in EN_VIVO for par in pares)):
            continue
        ini = float(cue['start'])
        tope = min(duracion - 0.2, ini + 6.0)
        sig = [c for c in cortes or [] if ini + 2.5 <= c <= tope]
        fin = sig[0] if sig else min(tope, ini + 4.5)
        if fin - ini < 2.0 or _estorba(piezas, ini, fin):
            continue
        capa = _capa_libre(piezas, ini, fin)
        if not capa:
            continue
        return {'pieza': 'rec', 'remotion': 'VisorRec', 'capa': capa, 'ini': round(ini, 3), 'fin': round(fin, 3),
                'motivo': 'visor REC: «' + ' '.join(r.get('texto', '') for r in cue.get('runs') or []) + '»',
                'valores': {'x0': round(100 * zx0, 2), 'y0': round(100 * zy0, 2), 'x1': round(100 * zx1, 2), 'y1': round(100 * zy1, 2), 'texto': 'REC'}}
    return None


# ------------------------------------------------------------------------------------------------ aro de luz en la cara
def _ancho_pildora(texto, U):
    try:
        import pila_planificador as PI
        f = PI._fuente(('Inter 24pt', 'Bold'), 30 * U)
        palabras = texto.split()
        return sum(f.getlength(w) for w in palabras) + 8 * U * max(0, len(palabras) - 1) + 48 * U
    except Exception:
        return 18 * U * len(texto) + 48 * U


def _aro(cues, W, H, piezas, caras_en, duracion):
    if caras_en is None:
        return None
    U = min(W, H * 9.0 / 16.0) / 1080.0
    zx0, zy0, zx1, zy1 = _zona(W, H)
    for n, cue in enumerate(cues[:-1]):
        if float(cue['start']) < 0.2 * duracion:
            continue
        planas = {plegar(r.get('texto') or '') for r in cue.get('runs') or []}
        if not planas & PERSONA:
            continue
        sig = cues[n + 1]
        ini = max(float(cue['start']), float(sig['start']) - 0.47)       # la píldora escribe la frase siguiente justo cuando empieza a decirse
        fin = min(float(sig['end']), float(sig['start']) + 1.9)
        if fin - ini < 1.2 or _estorba(piezas, ini, fin):
            continue
        try:
            vistas = [caras_en(t) for t in (ini + 0.1, (ini + fin) / 2.0, fin - 0.1)]
        except Exception:
            return None
        if not all(v and len(v) == 1 for v in vistas):
            continue                                                        # nadie, o más de una persona: el aro no sabría a quién rodear
        cajas = [v[0] for v in vistas]
        cxs = [(c[0] + c[2]) / 2.0 for c in cajas]
        cys = [(c[1] + c[3]) / 2.0 for c in cajas]
        altos = [c[3] - c[1] for c in cajas]
        if min(altos) < 0.07 or max(cxs) - min(cxs) > 0.05 or max(cys) - min(cys) > 0.04:
            continue                                                        # cara pequeña o que se mueve: el aro quedaría fuera de sitio
        cx, cy, alto = sum(cxs) / 3.0 * W, sum(cys) / 3.0 * H, sum(altos) / 3.0 * H
        r = 0.85 * alto
        r_max = min(cx - zx0 * W, zx1 * W - cx, cy - (zy0 - 0.02) * H, zy1 * H - cy)
        r = min(r, r_max)
        if r < 0.58 * alto:
            continue                                                        # tan cerca del borde que el aro cortaría la cara
        texto = ' '.join(str(x.get('texto') or '') for x in sorted(sig.get('runs') or [], key=lambda q: float(q.get('t') or 0))[:3]).strip()
        texto = texto[:1].upper() + texto[1:] if texto else ''
        if len(texto) > 26:
            texto = ' '.join(texto.split()[:2])
        w = _ancho_pildora(texto, U)
        lado = 'der' if cx + 0.5 * r + w <= zx1 * W else ('izq' if cx - 0.5 * r - w >= zx0 * W else '')
        if not lado or cy - 1.02 * r < zy0 * H - 0.02 * H:
            texto, lado = '', 'der'
        capa = _capa_libre(piezas, ini, fin)
        if not capa:
            continue
        return {'pieza': 'aro', 'remotion': 'AroCara', 'capa': capa, 'ini': round(ini, 3), 'fin': round(fin, 3),
                'motivo': 'aro de luz en la cara' + (f': «{texto}»' if texto else ''),
                'valores': {'cx': round(100 * cx / W, 3), 'cy': round(100 * cy / H, 3), 'r': round(100 * r / W, 3), 'texto': texto, 'lado': lado}}
    return None


# ------------------------------------------------------------------------------------------------ persianas en un corte
def _persianas(piezas, cortes, duracion, extra_iconos):
    cands = sorted((c for c in cortes or [] if 2.0 < c < duracion - 1.5), key=lambda c: abs(c - 0.5 * duracion))
    for c in cands:
        ini, fin = c - 0.25, c + 0.25
        if _estorba(piezas, ini - 0.15, fin + 0.15):
            continue
        capa = _capa_libre(piezas, ini, fin, extra_iconos)
        if not capa:
            continue
        return {'pieza': 'persianas', 'remotion': 'Persianas', 'capa': capa, 'ini': round(ini, 3), 'fin': round(fin, 3),
                'motivo': f'persianas en el corte de {c:.1f} s', 'valores': {'corte': 0.25}}
    return None


def _cortes_de(plan):
    """Los cortes de plano del plan en segundos: GO los da como [(t, fuerza)] (efectos_visuales.detectar_cortes, y los saltos de «quitar
    pausas» con fuerza 1) y, tras pasar por JSON, como listas; también vale un número suelto. (Hallado con el GO real: solo se leían números
    sueltos y la PRO no veía ningún corte: sin persianas y el zoom de entrada pegado a un corte.)"""
    out = []
    for c in plan.get('_cortes') or []:
        try:
            out.append(float(c[0]) if isinstance(c, (list, tuple)) else float(c))
        except (TypeError, ValueError, IndexError):
            continue
    return sorted(out)


# ------------------------------------------------------------------------------------------------ entrada con zoom y desenfoque
def entradas_zoom(plan, tramos=None, bloqueos=(), intro_fin=0.0, duracion=None):
    """Hasta 2 ENTRADAS de bloque con zoom y desenfoque (la referencia, «your Content»): el plano llega acercado ×1,12 y desenfocado y se asienta
    en ~0,3 s (en Resolve: una copia de V1 en PRO-ZOOM, debajo de los captions, con su comp de Fusion: colocar_pro._comp_zoom / comp_zoom del
    .lua). La primera, el primer bloque que se pueda pasado el gancho del inicio (en la 1.ª mitad); la segunda, pasado el 60 % y 8 s después.
    Nunca en el primer bloque, a menos de 0,35 s de un corte, en un bloque que va detrás de la persona, sobre el B-roll (`bloqueos`) ni
    con una escena a pantalla completa, las persianas o el aro en la cara (el aro sigue a la cara: el zoom lo descolocaría).
    Devuelve [{'t', 'dur', 'desenfoque' (px de un vertical de 1080)}]."""
    cues = _cues()
    piezas_ = [p for p in plan.get('piezas') or [] if not p.get('quitar')]
    if duracion is None:
        duracion = max([float(c['end']) for c in cues] + [float(p.get('fin') or 0) for p in piezas_] + [1.0])
    cortes = _cortes_de(plan)
    estorban = [(float(p['ini']) - m, float(p['fin']) + m) for p in piezas_
                for m in [1.5 if p.get('pieza') == 'persianas' else 0.2]       # (las persianas y el zoom, dos golpes fuertes: bien separados)
                if p.get('pantalla') or p.get('capa') == 'fondo' or p.get('persona') or p.get('pieza') in ('persianas', 'aro')]
    estorban += [(float(a), float(b)) for a, b in bloqueos or ()]
    candidatos = []
    for n, cue in enumerate(cues):
        a = float(cue['start'])
        if n == 0 or a < max(2.5, float(intro_fin or 0.0) + 0.5) or a > duracion - 1.5 or float(cue['end']) - a < 0.9:
            continue
        # (GO real: un corte 0,13 s antes y el zoom = dos sacudidas seguidas; JUSTO en el corte (±2 fotogramas) hace de transición y queda bien)
        if any(0.07 <= abs(a - c) < 0.6 for c in cortes) or _detras(cue, tramos):
            continue
        if any(x < a + ZOOM_DUR and a < y for x, y in estorban):
            continue
        candidatos.append(a)
    if not candidatos:
        return []
    elegidas = [next((a for a in candidatos if a <= 0.5 * duracion), candidatos[0])]
    segunda = next((a for a in candidatos if a >= max(0.6 * duracion, elegidas[0] + 8.0)), None)
    if segunda is not None:
        elegidas.append(segunda)
    return [{'t': round(a, 3), 'dur': ZOOM_DUR, 'desenfoque': ZOOM_DESENFOQUE} for a in elegidas]


# ------------------------------------------------------------------------------------------------ todo
def piezas(plan, W, H, mover=None, tramos=None, caras_en=None, duracion=None, fps=30.0):
    """Los motions de la referencia del Estilo 4 que le caben a este video (como mucho uno de cada), sin pisar lo que ya hay en el plan.
    `mover` = los bloques que movió la regla de la cara (fotogramas a `fps`, 'subir' en px), `tramos` = los que van detrás de la persona,
    `caras_en(t)` = las cajas de las caras en ese segundo (edicion_pro._caras), o None sin la IA de personas."""
    _FPS[0] = float(fps or 30.0)
    cues = _cues()
    actuales = list(plan.get('piezas') or [])
    if duracion is None:
        duracion = max([float(c['end']) for c in cues] + [float(p.get('fin') or 0) for p in actuales] + [1.0])
    cortes = _cortes_de(plan)
    iconos3d = [(float(c['ini']), float(c['fin'])) for c in plan.get('_iconos3d') or [] if 'ini' in c and 'fin' in c]
    nuevas = []
    for hacer in (lambda: _avion(cues, W, H, mover, tramos, actuales + nuevas, duracion, iconos3d) if cues else None,
                  lambda: _tachado(cues, W, H, mover, tramos, actuales + nuevas, iconos3d) if cues else None,
                  lambda: _rec(cues, W, H, actuales + nuevas, cortes, duracion) if cues else None,
                  lambda: _aro(cues, W, H, actuales + nuevas, caras_en, duracion) if cues else None,
                  lambda: _persianas(actuales + nuevas, cortes, duracion, iconos3d)):
        try:
            p = hacer()
        except Exception:
            try:
                import registro
                registro.excepcion(origen='edición PRO (motions del Estilo 4)')
            except Exception:
                pass
            p = None
        if p:
            nuevas.append(p)
    return nuevas
