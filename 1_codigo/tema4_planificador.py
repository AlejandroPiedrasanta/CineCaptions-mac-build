# CineCaptions · By Cinema Productions
# 1_codigo/tema4_planificador.py — Tema 4: captions blancos que se arman palabra a palabra en un recuadro, con la palabra clave grande y las conectoras pequeñas.
"""
tema4_planificador.py  (v5.4.33)
--------------------------------
Replica TEMA 4.mp4 (la referencia del usuario). Lo que hace ese estilo, medido sobre el video:

  * UN solo recuadro de texto, centrado en el cuadro (de 320 a 762 px de 1080: ≈ 41 % del ancho) y con la primera línea siempre en la misma altura (línea de base ≈ 57,6 % del alto);
    el texto cuelga hacia abajo y se alinea a la IZQUIERDA del recuadro (máximo dos líneas).
  * una sola tipografía (Inter Bold, blanca, letras apretadas, con un brillo suave) y TRES tamaños: la palabra CLAVE grande (×1,5), las normales (×1) y las CONECTORAS
    —es, lo, que, de, y…— pequeñas (×0,6), todas sobre la misma línea de base.
  * el tamaño se AJUSTA al recuadro: cada frase se escala para que su línea más ancha ocupe el ancho del recuadro (con un tope: una palabra suelta no se infla sin fin), por eso
    las frases cortas salen grandes y las largas pequeñas.
  * las palabras aparecen UNA A UNA, cada una en su sitio final, a medida que se dicen; cuando empieza la frase siguiente, la anterior desaparece.

Aquí se divide lo hablado en bloques de ≤ 6 palabras, se elige la clave de cada uno (los mismos puntajes del estilo «guion») y se calculan el tamaño y la posición de cada palabra con la
tipografía de verdad (Pillow). Salen los mismos datos que lee place_guion (un clip por palabra con su x, y y zoom): el pack «Tema4» (pack_tema4.py) pone la tipografía y el brillo.

    cues_de(palabras, idioma, pack, ancho_tl, mains=None, pesos=None, estilos_palabra=None, fin_video=None) -> (cues, plan)   (la misma forma que guion_planificador.cues_de)
"""
import guion_captions as GC
import guion_planificador as GP

PACK = 'Tema4'
FUENTE = ('Inter 24pt', 'Bold')
ANCHO, ALTO = 1080.0, 1920.0
CAJA_X0, CAJA_W = 320.0, 442.0            # el recuadro, en px de 1080 (medido en la referencia)
LINEA1_Y = 0.576                          # línea de base de la primera línea (fracción del alto)
EM_M_MAX = 58.0                           # tamaño de letra máximo de una palabra normal (px a 1080)
EM_MIN = 38.0                             # por debajo de esto una línea se lee mal: se prefiere otro corte
EM_BASE = 0.14 * GC.K_PX                  # el «Size» del pack × 640 px: lo que mide la letra a zoom 1
F_CLAVE, F_NORMAL, F_PEQ = 1.4, 1.0, 0.62  # tamaño relativo de cada clase
ESPACIADO = 0.95                          # CharacterSpacing del pack
HUECO = 0.12                              # hueco entre palabras (× la letra de la palabra anterior)
INTERLINEA = 0.92                         # de línea de base a línea de base (× la letra mayor de las dos líneas)
CENTRO_CAP = 0.364                        # el centro del texto está medio «alto de mayúscula» por encima de la línea de base
MAX_PESO = 5.5                            # un bloque pesa lo que sus palabras: normal 1, conectora 0,5 (la referencia parte «paquete de redes sociales más | vendido»)
MAX_PALABRAS = 7
MAX_CARACTERES = 38
MIN_LETRAS_CLAVE = 4                      # la palabra clave (la primera de la oración) tiene al menos tantas letras
AFINADO = {'adelanto': 0.03, 'hold': 0.25, 'gap_minimo': 0.06, 'min_bloque': 0.6, 'ancho': 1.0}
PEQ = set('''es lo de del y e o u un una el la los las en se'''.split())
PEQ_EN = set('''a an the and or of in on at to is it its as be by if so we my'''.split())
PEQ = PEQ | PEQ_EN


def _plano(t):
    return GP._plano(t)


def _ancho_em(texto):
    """Ancho de `texto` en «em» (1 = el tamaño de la letra) con la tipografía y el espaciado del pack."""
    f = GC._fuente(FUENTE, 200)
    if f is None:
        return len(texto) * 0.58 * ESPACIADO
    return f.getlength(texto) / 200.0 * ESPACIADO * AFINADO['ancho']


def _clase(pal, k, clave, pesos_orig):
    """'L' (clave) · 'M' (normal) · 'S' (conectora) de la palabra k."""
    if k == clave:
        return 'L'
    w = pal[k]
    if w['plano'] == 'que' and k > 0 and pal[k - 1]['plano'] == 'lo':
        return 'S'                                              # «es lo que»: pequeñas las tres
    forzado = next((pesos_orig[o] for o in w['orig'] if o in pesos_orig), None)
    if forzado == 'L':
        return 'S'
    if forzado == 'B':
        return 'M'
    return 'S' if w['plano'] in PEQ else 'M'


# ----------------------------------------------------------------------------------------------------------------------------- bloques
def _peso(pal, k):
    return 0.5 if pal[k]['plano'] in PEQ else 1.0


def _bloques(pal, frase):
    """Parte una frase en bloques que pesen a lo sumo MAX_PESO (palabra normal 1, conectora 0,5) y no pasen de MAX_CARACTERES: corta en los signos, nunca deja una conectora al final
    de un bloque (pasa al siguiente) ni deja suelta una conectora."""
    bloques, actual = [], []

    def cerrar():
        nonlocal actual
        if actual:
            bloques.append(actual)
            actual = []
    for pos, k in enumerate(frase):
        w = pal[k]
        peso = sum(_peso(pal, j) for j in actual) + _peso(pal, k)
        chars = sum(len(pal[j]['texto']) for j in actual) + len(actual) + len(w['texto'])
        if actual and (peso > MAX_PESO or chars > MAX_CARACTERES or len(actual) >= MAX_PALABRAS):
            if pal[actual[-1]]['plano'] in PEQ and len(actual) > 1:
                ultimo = actual.pop()                    # una conectora no cierra un bloque: pasa al siguiente
                cerrar()
                actual = [ultimo]
            else:
                cerrar()
        actual.append(k)
        signo = w['signo']
        coma = bool(signo) and signo in GP._COMA
        cierra = bool(signo) and signo in GP._FUERTE
        if cierra or (coma and sum(_peso(pal, j) for j in actual) >= 2.0):
            cerrar()
    cerrar()
    # una palabra suelta al final de una frase se lleva consigo el determinante que la precede («…hasta tu | negocio» → «…hasta | tu negocio»)
    for n in range(1, len(bloques)):
        if len(bloques[n]) == 1 and len(bloques[n - 1]) > 2 and (pal[bloques[n - 1][-1]]['plano'] in GP.DET or pal[bloques[n - 1][-1]]['plano'] in ('hasta', 'tu', 'su', 'mi'))                 and not (pal[bloques[n - 1][-1]]['signo'] and pal[bloques[n - 1][-1]]['signo'] in GP._FUERTE):
            bloques[n] = [bloques[n - 1].pop()] + bloques[n]
    return bloques


# ----------------------------------------------------------------------------------------------------------------------------- composición
def _ancho_linea(palabras):
    """Ancho (en «em de una palabra normal») de una línea: cada palabra a su tamaño relativo más el hueco entre ellas."""
    total = 0.0
    for i, (texto, clase) in enumerate(palabras):
        f = {'L': F_CLAVE, 'M': F_NORMAL, 'S': F_PEQ}[clase]
        total += _ancho_em(texto) * f
        if i:
            total += HUECO * f
    return total


def _em_linea(linea):
    """Letra (px a 1080) de una palabra normal en esa línea: la línea se escala hasta ocupar el recuadro (con un tope)."""
    return min(CAJA_W / max(_ancho_linea(linea), 0.01), EM_M_MAX)


def _componer(palabras):
    """palabras [(texto, clase)] -> k = cuántas van en la línea 1 (k = n: una sola línea). CADA línea se ajusta al recuadro por su cuenta (una línea corta sale grande, con tope); se
    prueba cada corte y gana el de letras más grandes en las dos líneas, con la primera línea larga y las dos parecidas."""
    n = len(palabras)
    mejor = None
    for k in range(1, n + 1):
        l1, l2 = palabras[:k], palabras[k:]
        e1 = _em_linea(l1)
        if not l2:
            puntaje = e1
        else:
            e2 = _em_linea(l2)
            w1, w2 = _ancho_linea(l1) * e1, _ancho_linea(l2) * e2          # lo que miden de verdad (px)
            puntaje = (e1 + e2) / 2.0
            if w2 > w1 + 1.0:
                puntaje -= 6.0                                              # la primera línea es la larga
            if l1[-1][1] == 'S':
                puntaje -= 1.5
            if len(l2) == 1 and l2[0][1] == 'S':
                puntaje -= 8.0                                              # una conectora no se queda sola
            puntaje -= 4.0 * abs(w1 - w2) / max(w1, w2)
            puntaje -= 3.0 if min(e1, e2) < EM_MIN else 0.0
            if palabras[0][1] == 'L' and k >= 1 and all(c == 'S' for _t, c in l1[1:]) and (not l2 or l2[0][1] != 'S'):
                puntaje += 8.0                                              # «Historias de | lunes a viernes»: la clave abre la línea con sus conectoras
        if mejor is None or puntaje > mejor[0]:
            mejor = (puntaje, k)
    return mejor[1]


def _disponer(palabras):
    """Posición y tamaño de cada palabra del bloque: [{'x','y','em','linea','clase'}] (px de 1080×1920; x,y = centro) y la caja (arriba, abajo) en px. Cada línea va CENTRADA en el recuadro."""
    k = _componer(palabras)
    lineas = [palabras[:k], palabras[k:]] if k < len(palabras) else [palabras]
    sal = []
    base = LINEA1_Y * ALTO
    em_prev = None
    for n_l, linea in enumerate(lineas):
        em_m = _em_linea(linea)
        ems = [em_m * {'L': F_CLAVE, 'M': F_NORMAL, 'S': F_PEQ}[c] for _t, c in linea]
        em_l = max(ems)
        if n_l:
            base += INTERLINEA * max(em_l, em_prev)
        anchos = [_ancho_em(texto) * em for (texto, _c), em in zip(linea, ems)]
        huecos = [HUECO * em_m * (0.8 if linea[i + 1][1] == 'S' else 1.0) for i in range(len(linea) - 1)]
        total = sum(anchos) + sum(huecos)
        x = CAJA_X0 + (CAJA_W - total) / 2.0
        for i, ((texto, clase), em, ancho) in enumerate(zip(linea, ems, anchos)):
            if i:
                x += huecos[i - 1]
            sal.append({'x': x + ancho / 2.0, 'y': base - CENTRO_CAP * em, 'em': em, 'linea': n_l, 'clase': clase})
            x += ancho
        em_prev = em_l
    arriba = LINEA1_Y * ALTO - 0.73 * max(s['em'] for s in sal if s['linea'] == 0)
    abajo = base + 0.22 * max(s['em'] for s in sal if s['linea'] == len(lineas) - 1)
    return sal, (arriba, abajo)


# ----------------------------------------------------------------------------------------------------------------------------- el plan
def planificar(palabras, idioma='es', pack=PACK, ancho_tl=1080, ancla='medio', mains=None, estilos=None, fin_video=None, pesos=None, estilos_palabra=None, **_):
    """palabras [{'word','start','end'}] -> (cues, plan). La misma firma que guion_planificador.planificar (los parámetros que no aplican a este estilo se ignoran)."""
    A = AFINADO
    pal = GP._preparar(palabras)
    if not pal:
        return [], []
    forzados = None
    if mains:
        forzados = set()
        pedidos = {_plano(str(m)) for m in mains if not isinstance(m, int)}
        forzados |= {k['i'] for k in pal if k['plano'] in pedidos}
        idx = {int(m) for m in mains if isinstance(m, int)}
        forzados |= {k['i'] for k in pal if idx & set(k['orig'])}
    pesos_orig = dict(pesos or {})
    plan, cues = [], []
    bloques = []
    for n_frase, frase in enumerate(GP.frases(pal)):
        for b in _bloques(pal, frase):
            bloques.append((n_frase, b))
    sin_clave = 0
    for n, (n_frase, idx_b) in enumerate(bloques):
        if forzados is not None:
            claves = GP.elegir_mains(pal, idx_b, forzados=forzados)
            clave = claves[0] if claves else None
        else:
            clave = None
            if n == 0 or bloques[n - 1][0] != n_frase:           # el primer bloque de cada frase: su primera palabra, si es de las que pesan
                k0 = next((k for k in idx_b if pal[k]['plano'] not in PEQ), None)
                if k0 is not None and k0 == idx_b[0] and len(pal[k0]['plano']) >= MIN_LETRAS_CLAVE:
                    clave = k0
            if clave is None and sin_clave >= 2:                 # ritmo: como en la referencia, una de cada tres frases lleva una palabra grande (la que más pesa)
                pts = GP.puntajes(pal, idx_b)
                if pts:
                    mejor = max(pts, key=lambda k: (pts[k], len(pal[k]['plano'])))
                    if pts[mejor] >= GP.AFINADO['puntaje_min'] and pal[mejor]['plano'] not in PEQ and sum(_peso(pal, j) for j in idx_b) <= 4.5:
                        clave = mejor
            sin_clave = 0 if clave is not None else sin_clave + 1
        clases = [_clase(pal, k, clave, pesos_orig) for k in idx_b]
        textos = [pal[k]['texto'] for k in idx_b]
        if textos:
            textos[0] = textos[0][:1].upper() + textos[0][1:]
        disp, caja = _disponer(list(zip(textos, clases)))
        t0 = pal[idx_b[0]]['t'] - A['adelanto']
        sig_t0 = (pal[bloques[n + 1][1][0]]['t'] - A['adelanto']) if n + 1 < len(bloques) else None
        ultimo_fin = pal[idx_b[-1]]['fin']
        t1 = ultimo_fin + A['hold']
        if sig_t0 is not None:
            t1 = min(t1, sig_t0 - A['gap_minimo'])
        elif fin_video:
            t1 = max(t1, min(float(fin_video), ultimo_fin + 1.0))
        t1 = max(t1, t0 + A['min_bloque'])
        if sig_t0 is not None and t1 > sig_t0 - 0.02:
            t1 = max(t0 + 0.3, sig_t0 - 0.02)
        runs = []
        for k, texto, clase, d in zip(idx_b, textos, clases, disp):
            r = {'rol': {'L': 'main', 'M': 'complement', 'S': 'context'}[clase], 'texto': texto, 't': round(max(0.0, pal[k]['t'] - A['adelanto']), 3),
                 'x': round(d['x'] / ANCHO, 4), 'y': round(d['y'] / ALTO, 4)}
            z = d['em'] / EM_BASE
            if abs(z - 1.0) > 0.005:
                r['zoom'] = round(z, 3)
            runs.append(r)
        cue = {'start': round(max(0.0, t0), 3), 'end': round(t1, 3), 'estilo': 1, 'runs': runs, 'caja': [round(caja[0] / ALTO, 4), round(caja[1] / ALTO, 4)]}
        cues.append(cue)
        orig = sorted(o for k in idx_b for o in pal[k]['orig'])
        plan.append({'frase': n_frase, 'palabras': list(idx_b), 'mains': [clave] if clave is not None else [], 'grupos': {}, 'miembros': set(), 'orig': orig,
                     't0': cue['start'], 't1': cue['end'], 'estilos': [1] if clave is not None else [], 'estilo_bloque': 1,
                     'grandes': sorted(o for o in pal[clave]['orig']) if clave is not None else [],
                     'pesos': {o: ('B' if c == 'M' else 'L') for k, c in zip(idx_b, clases) if c != 'L' for o in pal[k]['orig']}})
    return cues, plan


def cues_de(palabras, idioma='es', pack=PACK, ancho_tl=1080, **kw):
    """La misma forma que guion_planificador.cues_de: (cues listos para el JSON de place_guion, plan)."""
    return planificar(palabras, idioma, pack, ancho_tl, **kw)


def resumen(cues):
    """El plan en una tabla legible (para depurar)."""
    filas = []
    for c in cues:
        partes = []
        for r in c['runs']:
            marca = {'main': '▲', 'complement': '', 'context': '·'}[r['rol']]
            partes.append(f"{marca}{r['texto']}")
        filas.append(f"{c['start']:6.2f}-{c['end']:6.2f}  " + ' '.join(partes))
    return '\n'.join(filas)
