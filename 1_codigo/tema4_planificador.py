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
HUECO = 0.28                              # hueco entre palabras (× la letra normal de la línea). v5.5.8: era 0,12; MEDIDO en el render a 1080 de Resolve: 7 px con letra de 58 px y se leían pegadas («Numberone», «stopoversizing»)
INTERLINEA = 0.92                         # de línea de base a línea de base (× la letra mayor de las dos líneas)
CENTRO_CAP = 0.364                        # el centro del texto está medio «alto de mayúscula» por encima de la línea de base
MAX_PESO = 5.5                            # un bloque pesa lo que sus palabras: normal 1, conectora 0,5 (la referencia parte «paquete de redes sociales más | vendido»)
MAX_PALABRAS = 7
MAX_CARACTERES = 38
MIN_LETRAS_CLAVE = 4                      # la palabra clave (la primera de la oración) tiene al menos tantas letras
AFINADO = {'adelanto': 0.03, 'hold': 0.25, 'gap_minimo': 0.06, 'min_bloque': 0.6, 'ancho': 1.08}   # v5.5.8 'ancho' 1,0 → 1,08: MEDIDO en el render de Resolve (Tema 5, 1080 px), cada palabra sale un 5–13 % más ancha que lo que mide Pillow
PEQ = set('''es lo de del y e o u un una el la los las en se'''.split())
PEQ_EN = set('''a an the and or of in on at to is it its as be by if so we my'''.split())
PEQ = PEQ | PEQ_EN

# v5.5.8 — los Temas 5 y 6 con captions Text+ EDITABLES: los mismos bloques y tiempos que el Tema 4, pero con el diseño de sus captions de Remotion
# (remotion/src/Subtitulo.tsx): lo que se dice en una letra pequeña blanca y la FRASE CLAVE grande en otra letra y otro color, en su propia línea
# (o en la de las 1-2 palabras cortas de delante), todas las líneas centradas alrededor de `y`. Los packs «Tema5»/«Tema6» (pack_tema5.py) llevan
# una variante por color de la clave: el bloque elige la suya (`estilo` del cue). 'S' y 'K' son los de Subtitulo.tsx (fracción del lado corto).
DISENOS = {
    'Tema5': {'estilo': 'skill', 'sans': ('Inter 18pt', 'Medium'), 'serif': ('DM Serif Text', 'Italic'), 'S': 0.035, 'K': 2.4, 'y': 0.56,
              'alto_serif': 0.98, 'alto_sans': 1.32, 'tam_sans': 0.065, 'tam_serif': 0.15, 'esp_sans': 0.995, 'esp_serif': 0.99,
              'variantes': ('azul', 'ambar', 'lima', 'lila')},              # = edicion_pro_tema5.ACENTOS (el de acento_de_video)
    'Tema6': {'estilo': 'editorial', 'sans': ('Instrument Serif', 'Regular'), 'serif': ('Instrument Serif', 'Regular'), 'S': 0.048, 'K': 2.3,
              'y': 0.52, 'alto_serif': 0.9, 'alto_sans': 1.18, 'tam_sans': 0.085, 'tam_serif': 0.19, 'esp_sans': 0.985, 'esp_serif': 0.985,
              'variantes': ('lima', 'blanco')},                             # = edicion_pro_tema6.LIMA / BLANCO (color_clave)
}
HUECO_SKILL = 0.27                        # hueco entre palabras (× la letra de la palabra que sigue), como Subtitulo.tsx
MAX_ANCHO_SKILL = 0.86                    # la línea más ancha cabe en el 86 % del ancho
LETRAS_SANS = 34                          # una línea de la letra pequeña lleva ~34 letras
AIRE_SKILL = 0.12                         # aire mínimo entre las letras de dos líneas (× la letra pequeña)
# Lo que mide de verdad cada tipografía en el render de Resolve frente a Pillow: 'em' (la letra que pinta Fusion por unidad de «Size» × K_PX) y
# 'ancho' (lo que queda: ancho de la palabra a esa letra). Fusion escala cada tipografía por su alto de línea (ascendente + descendente de hhea):
# em ≈ 1,30 / (asc + desc). MEDIDO (v5.5.8, render a 1080 de Resolve Studio): Instrument Serif (1,30) sale con el ancho de Pillow (tinta = 0,955 del
# avance × 0,985 de espaciado: las letras justas) y los centros a ±4 px. Inter 24pt Bold: el 1,08 del Tema 4 (con su ESPACIADO 0,95; em sin tocar).
CALIBRADO = {('Inter 24pt', 'Bold'): {'ancho': 1.08, 'em': 1.0},
             ('Instrument Serif', 'Regular'): {'ancho': 1.0, 'em': 1.0},
             ('Inter 18pt', 'Medium'): {'ancho': 1.0, 'em': 1.074},       # 1,30 / 1,21 (el Inter Bold del Tema 4 midió 1,06–1,08)
             ('DM Serif Text', 'Italic'): {'ancho': 1.0, 'em': 0.948}}    # 1,30 / 1,371 (medido: alto 94 px / 91 previstos)


def _calibrado(fuente):
    return CALIBRADO.get(tuple(fuente)) or {'ancho': AFINADO['ancho'], 'em': 1.0}


def _metricas(fuente):
    """(línea de base dentro de una línea de alto 1 em —como el navegador—, centro vertical del Text+ sobre la línea de base), en em."""
    try:
        asc, desc = (v / 200.0 for v in GC._fuente(tuple(fuente), 200).getmetrics())     # (Pillow: ascender y descender de hhea, en px)
    except Exception:
        asc, desc = 0.969, 0.241
    return (1.0 + asc - desc) / 2.0, (asc - desc) / 2.0              # Inter: 0,864 y 0,364 (= CENTRO_CAP, medido en Resolve)


def _tinta(texto, fuente):
    """(arriba, abajo) de las letras de `texto` respecto a su línea de base, en em (arriba < 0)."""
    try:
        b = GC._fuente(tuple(fuente), 200).getbbox(texto, anchor='ls')
        return b[1] / 200.0, b[3] / 200.0
    except Exception:
        return -0.75, 0.2


def _plano(t):
    return GP._plano(t)


def _ancho_em(texto, fuente=FUENTE, espaciado=ESPACIADO):
    """Ancho de `texto` en «em» (1 = el tamaño de la letra) con la tipografía y el espaciado del pack (v5.5.8: la de cada clase de palabra)."""
    f = GC._fuente(tuple(fuente), 200)
    if f is None:
        return len(texto) * 0.58 * espaciado
    return f.getlength(texto) / 200.0 * espaciado * _calibrado(fuente)['ancho']


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
def _tiempos(pal, bloques, n, fin_video):
    """(t0, t1) del bloque n: entra con su primera palabra y se queda hasta que entra el siguiente (o un poco tras su última palabra)."""
    A = AFINADO
    idx_b = bloques[n][1]
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
    return t0, t1


def planificar(palabras, idioma='es', pack=PACK, ancho_tl=1080, ancla='medio', mains=None, estilos=None, fin_video=None, pesos=None, estilos_palabra=None,
               video=None, **_):
    """palabras [{'word','start','end'}] -> (cues, plan). La misma firma que guion_planificador.planificar (los parámetros que no aplican a este estilo se ignoran).
    `video` (Tema 5): de él sale el color de la frase clave (edicion_pro_tema5.acento_de_video); sin él, el azul."""
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
    if pack in DISENOS:                                          # v5.5.8: Temas 5 y 6 (Text+ editables con el diseño de sus captions de Remotion)
        return _planificar_skill(pal, bloques, DISENOS[pack], forzados, fin_video, video)
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
        t0, t1 = _tiempos(pal, bloques, n, fin_video)
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


# ----------------------------------------------------------------------------------------------------------------------------- Temas 5 y 6
def _lineas_skill(ps):
    """Las líneas de Subtitulo.tsx: [antes] [frase clave] [después]; lo de antes sube a la línea de la clave si son 1-2 palabras cortas.
    -> [(índices, es_la_de_la_clave)]"""
    def sans(desde, hasta):
        ls, letras = [], 0
        for i in range(desde, hasta):
            if not ls or letras + len(ps[i]['texto']) > LETRAS_SANS:
                ls.append(([], False))
                letras = 0
            ls[-1][0].append(i)
            letras += len(ps[i]['texto']) + 1
        return ls
    claves = [i for i, w in enumerate(ps) if w.get('clave')]
    if not claves:
        return sans(0, len(ps))
    k0, k1 = claves[0], claves[-1]
    antes, despues = sans(0, k0), sans(k1 + 1, len(ps))
    clave = list(range(k0, k1 + 1))
    if 0 < k0 <= 2 and sum(len(ps[i]['texto']) + 1 for i in range(k0)) <= 10:
        return [(antes[0][0] + clave, True)] + despues
    return antes + [(clave, True)] + despues


def _disponer_skill(ps, D):
    """Posición y tamaño de cada palabra como en Subtitulo.tsx (px de 1080×1920; x, y = centro del Text+): [{'x','y','em','clave'}] y la caja
    (arriba, abajo) en px. Cada palabra se mide con SU tipografía (la pequeña o la de la clave)."""
    S = D['S'] * min(ANCHO, ALTO)
    lineas = _lineas_skill(ps)
    fuente = [D['serif'] if w.get('clave') else D['sans'] for w in ps]
    rel = [D['K'] if w.get('clave') else 1.0 for w in ps]
    anchos = [_ancho_em(w['texto'], fuente[i], D['esp_serif'] if w.get('clave') else D['esp_sans']) for i, w in enumerate(ps)]

    def ancho_linea(idx, s):
        return sum(anchos[i] * rel[i] * s + (HUECO_SKILL * rel[i] * s if n else 0.0) for n, i in enumerate(idx))
    mayor = max(ancho_linea(idx, S) for idx, _c in lineas)
    if mayor > MAX_ANCHO_SKILL * ANCHO:
        S *= MAX_ANCHO_SKILL * ANCHO / mayor
    altos = [max(rel[i] for i in idx) * S * D['alto_serif'] if es_clave else S * D['alto_sans'] for idx, es_clave in lineas]
    sal = [None] * len(ps)
    top, tinta_prev = 0.0, None
    for (idx, _c), h in zip(lineas, altos):
        base = top + max(_metricas(fuente[i])[0] * rel[i] * S for i in idx)   # las palabras de la línea comparten la línea de base
        tintas = [_tinta(ps[i]['texto'], fuente[i]) for i in idx]
        if tinta_prev is not None:                                # en Remotion la serif y la sans se tocan: aquí no se pisan (descendentes de la clave)
            pisa = tinta_prev + AIRE_SKILL * S - (base + min(t[0] * rel[i] * S for t, i in zip(tintas, idx)))
            if pisa > 0:
                base += pisa
                top += pisa
        x = (ANCHO - ancho_linea(idx, S)) / 2.0
        for n, i in enumerate(idx):
            em = rel[i] * S
            if n:
                x += HUECO_SKILL * em
            w = anchos[i] * em
            sal[i] = {'x': x + w / 2.0, 'y': base - _metricas(fuente[i])[1] * em, 'em': em, 'clave': bool(ps[i].get('clave'))}
            x += w
        tinta_prev = base + max(t[1] * rel[i] * S for t, i in zip(tintas, idx))
        top += h
    arriba = D['y'] * ALTO - top / 2.0                            # el bloque, centrado en `y`
    for s in sal:
        s['y'] += arriba
    return sal, (arriba, arriba + top)


_ACENTO_CACHE = {}


def _variante_acento(D, video):
    """Tema 5: la variante del pack con el color de acento del video (edicion_pro_tema5.acento_de_video; sin video, la del azul)."""
    import edicion_pro_tema5 as T5
    clave = None
    if video:
        try:
            from pathlib import Path
            clave = (str(video), Path(video).stat().st_mtime)
        except OSError:
            clave = None
    if clave is not None and clave not in _ACENTO_CACHE:
        _ACENTO_CACHE[clave] = T5.acento_de_video(video)
    hexa = _ACENTO_CACHE.get(clave) or T5.ACENTOS['azul']
    nombre = next((k for k, v in T5.ACENTOS.items() if v == hexa), 'azul')
    return D['variantes'].index(nombre) + 1 if nombre in D['variantes'] else 1


def _planificar_skill(pal, bloques, D, forzados, fin_video, video):
    """Los cues de los Temas 5 y 6 (mismos bloques y tiempos que el Tema 4): la frase clave de cada bloque como la eligen sus captions de Remotion
    (edicion_pro_tema5.marcar_claves; con marcas de Creativo, las palabras marcadas «Principal»), rol 'main' = la clave (variante del color) y
    'complement' = lo demás."""
    import edicion_pro_tema5 as T5
    editorial = D['estilo'] == 'editorial'
    A = AFINADO
    grupos = []
    for n, (n_frase, idx_b) in enumerate(bloques):
        inicio = n == 0 or bloques[n - 1][0] != n_frase              # a mitad de frase el bloque sigue en minúscula (como Remotion)
        ps = []
        for j, k in enumerate(idx_b):
            texto = pal[k]['texto']
            if j == 0 and inicio:
                texto = texto[:1].upper() + texto[1:]
            ps.append({'texto': texto, 'k': k})
        if forzados is not None:
            for w in ps:
                w['clave'] = w['k'] in forzados
        else:
            T5._marcar_claves(ps)
        grupos.append(ps)
    if editorial:
        import edicion_pro_tema6 as T6
        temas = T6.temas_del_video([{'palabras': ps} for ps in grupos], frozenset(T5.DEBILES)) if forzados is None else set()
        if forzados is None:
            for ps in grupos:
                T5.marcar_claves(ps, editorial=True)              # cada bloque con su línea grande
        variantes = [D['variantes'].index('lima' if T6.color_clave(ps, temas, frozenset(T5.ENFASIS)) == T6.LIMA else 'blanco') + 1 for ps in grupos]
    else:
        variantes = [_variante_acento(D, video)] * len(grupos)
    cues, plan = [], []
    for n, ((n_frase, idx_b), ps, estilo) in enumerate(zip(bloques, grupos, variantes)):
        disp, caja = _disponer_skill(ps, D)
        t0, t1 = _tiempos(pal, bloques, n, fin_video)
        runs = []
        for w, d in zip(ps, disp):
            clave = d['clave']
            r = {'rol': 'main' if clave else 'complement', 'texto': w['texto'], 't': round(max(0.0, pal[w['k']]['t'] - A['adelanto']), 3),
                 'x': round(d['x'] / ANCHO, 4), 'y': round(d['y'] / ALTO, 4)}
            fuente = D['serif'] if clave else D['sans']
            z = d['em'] / ((D['tam_serif'] if clave else D['tam_sans']) * GC.K_PX * _calibrado(fuente)['em'])
            if abs(z - 1.0) > 0.005:
                r['zoom'] = round(z, 3)
            runs.append(r)
        cue = {'start': round(max(0.0, t0), 3), 'end': round(t1, 3), 'estilo': estilo, 'runs': runs, 'caja': [round(caja[0] / ALTO, 4), round(caja[1] / ALTO, 4)]}
        cues.append(cue)
        claves = [w['k'] for w in ps if w.get('clave')]
        plan.append({'frase': n_frase, 'palabras': list(idx_b), 'mains': claves, 'grupos': {}, 'miembros': set(),
                     'orig': sorted(o for k in idx_b for o in pal[k]['orig']), 't0': cue['start'], 't1': cue['end'],
                     'estilos': [estilo] if claves else [], 'estilo_bloque': estilo,
                     'grandes': sorted(o for k in claves for o in pal[k]['orig']),
                     'pesos': {o: 'B' for w in ps if not w.get('clave') for o in pal[w['k']]['orig']}})
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
