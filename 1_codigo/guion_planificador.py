# CineCaptions · By Cinema Productions
# 1_codigo/guion_planificador.py — del texto con tiempos (ASR) a los bloques del estilo «guion»: frases, palabra grande, negritas, pila, estilo y momento.
"""
guion_planificador.py  (v5.9)
-----------------------------
Convierte las palabras con tiempos que entrega la voz en los bloques que arma guion_captions.construir_cues, imitando lo que hace a mano el
editor de la referencia (REFERENCIA.mp4, medida en guion_referencia.py):

  1. FRASES: se corta en los signos fuertes (. ? ! …), en las comas con pausa y en las pausas largas.
  2. PALABRA GRANDE: en cada frase se puntúan las palabras (largas, sustantivos tras artículo, adjetivos evaluativos, última palabra…) y se eligen
     una o dos (separadas ≥ 4 palabras). Las frases cortas «de reacción» («se pasaron», «a ver») se quedan sin palabra grande.
  3. BLOQUES: entre dos palabras grandes la frase se parte donde hay pausa y sin dejar un artículo colgando; cada bloque tiene a lo sumo
     {MAX_PALABRAS} palabras y una o dos palabras grandes.
  4. LÍNEAS: lo que se dice antes de la grande va arriba, la grande en medio y lo que sigue abajo; las líneas pequeñas son finas con UNA palabra
     (o grupo) en negrita. La pila se centra en un ancla vertical y las alturas salen del tamaño de cada línea.
  5. ESTILO: por ORACIÓN, como la referencia (5·5·5, 2·2): los bloques de una oración comparten estilo de base (Luxe) y cada oración nueva estrena el
     siguiente; el primer bloque (gancho) lleva el suyo; el remate de una oración con varias palabras grandes lleva un acento de Amro (pastilla,
     subrayado); un pequeño léxico manda sobre todo (fuego → Fire, negación → Strike…). Los presets de Amro NUNCA son la base de una oración.
  6. TIEMPOS: cada palabra entra cuando se dice; la pila entera se va un instante después de la última palabra, sin pisar el bloque siguiente.

Todo es determinista (mismo audio → mismos bloques) y se puede forzar a mano: `mains=` (palabras o índices) y `estilos=` (por índice de bloque).
`evaluar()` compara el resultado con guion_referencia.BLOQUES (palabra grande, límites de bloque, estilo).
"""
import re

import guion_captions as G

MAX_PALABRAS = 8
ANCLAS = {'medio': 0.56, 'alto': 0.33, 'bajo': 0.68}
ESTILOS_BASE = (1, 2, 4, 5)                  # Luxe: el estilo «de fondo» de cada oración (pack «Referencia»: en el orden en que los estrena la referencia)
ESTILOS_ACENTO = (3, 8)                      # presets de Amro sueltos (pastilla, subrayado): el REMATE de la oración; fuego (6) y negación (7) van por significado
ROTACION = ESTILOS_BASE + ESTILOS_ACENTO + (6, 7)
ESTILOS_FUEGO = (6,)
# v5.5: los estilos Luxe de base (1, 2, 4, 5) tienen tres formas de BARRIDO DE LUZ en el pack: el original (sutil), «Screen» (una banda de luz de color que se suma) y «Sólido» (una banda opaca).
# {estilo base: (original, screen, sólido)}; las palabras grandes los van alternando para que el barrido (y su color) no se repita. Sólo cuando el pack trae esas variantes (9-16).
BARRIDOS = {1: (1, 9, 13), 2: (2, 10, 14), 4: (4, 11, 15), 5: (5, 12, 16)}
ESTILOS_NEGACION = (7,)
AFINADO = {'adelanto': 0.03, 'hold': 0.22, 'min_bloque': 0.7, 'gap_minimo': 0.06, 'puntaje_min': 8.0, 'puntaje_2': 9.0, 'dist_mains': 4,
           'pausa_frase': 0.45, 'pausa_coma': 0.12, 'combinar_s': 2.0, 'cap_len': 10, 'bonus_det': 4.0, 'bonus_ultima': 4.0, 'bonus_gancho': 8.0,
           'pen_verbo': 3.0, 'pen_pret': 6.0, 'pen_modifica': 2.0, 'bonus_adj': 3.0, 'bonus_cond': 5.0, 'hueco': 0.03, 'cabe': 0.96, 'alto_linea': 0.039,
           'pausa_oracion': 0.3}      # fin de oración sin signos: en la referencia los finales dejan ≥0,32 s y las comas ≤0,24 s

_ES_STOP = set('''a al ante bajo cabe con contra de del desde durante en entre hacia hasta mediante para por segun sin so sobre tras
el la los las un una unos unas lo le les me te se nos os mi mis tu tus su sus que quien cual cuyo como cuando donde cuanto y e o u ni pero mas
sino aunque porque pues si no ya muy tan este esta estos estas ese esa esos esas aquel aquella aquellos aquellas eso esto aquello yo tu el ella
nosotros ellos ellas usted ustedes es son era fue fueron ser esta estan estoy estamos estaba ha han he hemos hay habia tiene tengo tienen tenia
va van voy vamos iba fui seamos sea sean sera soy eres somos jajaja jaja eh ah oh mmm'''.split())
_EN_STOP = set('''a an the and or but nor so yet of in on at to for from by with without about into over after before between under again then than
i you he she it we they me him her us them my your his its our their this that these those is are was were be been am do does did have has had
will would can could should shall may might not no just very too also'''.split())
STOP = _ES_STOP | _EN_STOP
# palabras que llevan al sustantivo de la derecha (artículos, posesivos, preposiciones): la palabra que las sigue es «cabeza» del grupo
DET = set('''el la los las un una unos unas mi mis tu tus su sus este esta estos estas ese esa esos esas de del sin con por para en a al
the a an my your our their this that these those of with without for in on to'''.split())
_FIN_PRET = ('aron', 'ieron', 'eron', 'aban', 'ieres', 'ieran')       # verbos conjugados: casi nunca son lo que se quiere destacar
_FIN_VERBO = ('amos', 'emos', 'imos', 'aste', 'iste', 'ando', 'iendo')
_FIN_ADJ = ('osa', 'oso', 'osas', 'osos', 'isima', 'isimo', 'isimas', 'isimos', 'ante', 'iva', 'ivo', 'ful', 'ous')
_FIN_COND = ('ria', 'rias', 'riamos', 'rian')
# léxico mínimo de intención: la palabra pide un estilo concreto del pack (se usa el primero que no repita al bloque anterior)
_FUEGO = set('fuego humo caliente candela hot fire smoke lit fuegos quema quemar arde ardiendo explosion explosión'.split())
_NEGAR = set('nunca jamas jamás nadie nada mal peor error fallo no sin never nothing worst wrong fail fatal mentira'.split())

_APERTURAS = {'a ver', 'oye', 'mira', 'bueno', 'pues', 'vale', 'ok', 'okay', 'entonces', 'ojo', 'ah', 'eh', 'oh', 'look', 'so', 'well', 'listen', 'hey', 'wait'}
_CONJ = {'o', 'pero', 'y', 'pues', 'porque', 'sino', 'aunque', 'but', 'and', 'or', 'because', 'so', 'then'}
_FUERTE = '.?!…'
_COMA = ',;:'


def _plano(t):
    """minúsculas sin tildes ni signos (para comparar)."""
    t = re.sub(r'[^\w]', '', (t or '').lower().replace('ñ', '\x00')).replace('\x00', 'ñ')
    for a, b in (('á', 'a'), ('é', 'e'), ('í', 'i'), ('ó', 'o'), ('ú', 'u'), ('ü', 'u')):
        t = t.replace(a, b)
    return t


def limpiar(texto):
    """El texto tal como se dibuja: sin signos de apertura/cierre pegados."""
    return re.sub(r'^[¿¡"\'(\[«]+|[.,;:!?…"\')\]»]+$', '', (texto or '').strip())


def _signo_final(texto):
    m = re.search(r'([.,;:!?…]+)["\')\]»]*$', (texto or '').strip())
    return m.group(1)[-1] if m else ''


def _es_contenido(plano):
    return len(plano) >= 4 and plano not in STOP


def _preparar(palabras):
    """[{'i','texto','plano','t','fin','signo'}] sin palabras vacías."""
    sal = []
    for j, p in enumerate(palabras):
        txt = limpiar(p.get('word', ''))
        if not txt:
            continue
        plano = _plano(txt)
        fin = float(p.get('end', p.get('start', 0.0)))
        if sal and plano == sal[-1]['plano'] and plano in STOP and len(plano) <= 5 and float(p.get('start', 0.0)) - sal[-1]['fin'] < 0.6:
            sal[-1]['fin'] = max(sal[-1]['fin'], fin)               # tartamudeo («este este», «de de»): una sola vez, con el tiempo de las dos
            sal[-1]['signo'] = _signo_final(p.get('word', '')) or sal[-1]['signo']
            sal[-1]['orig'].append(j)
            continue
        sal.append({'i': len(sal), 'orig': [j], 'texto': txt, 'plano': plano, 't': float(p.get('start', 0.0)), 'fin': fin,
                    'signo': _signo_final(p.get('word', '')), 'fin_frase': bool(p.get('fin_frase'))})
    return sal


def frases(pal, A=AFINADO):
    """Parte las palabras en frases: signo fuerte, coma con pausa, pausa larga o demasiadas palabras. Devuelve listas de índices."""
    salida, actual = [], []
    for k, w in enumerate(pal):
        actual.append(k)
        sig = w['signo']
        sig_gap = (pal[k + 1]['t'] - w['fin']) if k + 1 < len(pal) else 9.0
        corta = (bool(sig) and sig in _FUERTE and (len(actual) >= 2 or sig_gap > 0.3)) or sig_gap >= A['pausa_frase']
        if not corta and sig and sig in _COMA and ((len(actual) >= 3 and sig_gap >= A['pausa_coma']) or (len(actual) == 2 and sig_gap >= 0.2)):
            corta = True
        if not corta and w['fin_frase'] and len(actual) >= 2 and k + 1 < len(pal):
            corta = True                     # la app ya marcó el fin de frase (con los signos que la IA luego quita)
        if not corta and len(actual) >= 2 and sig_gap >= 0.22:
            corta = True                     # una pausa de 0,2 s sin coma escrita (los signos se quitaron) hace de coma
        if not corta and len(actual) <= 2 and ' '.join(pal[j]['plano'] for j in actual) in _APERTURAS and k + 1 < len(pal):
            corta = True                     # «a ver», «oye», «bueno»…: se dicen solos y luego viene la frase
        if not corta and k + 1 < len(pal) and pal[k + 1]['plano'] in _CONJ and sig_gap >= 0.2 and len(actual) >= 2:
            corta = True                     # «…boda | o prefieres…»: antes de una conjunción con pausa
        if corta and not (bool(sig) and sig in _FUERTE) and len(actual) < MAX_PALABRAS and w['plano'] in STOP and len(w['plano']) <= 4 \
                and sig_gap < 1.0 and k + 1 < len(pal):
            corta = False                    # una pausa NO corta tras un artículo/«no»/«que»…: la frase sigue («que en este caso no | está funcionando»)
        if corta:
            salida.append(actual)
            actual = []
    if actual:
        salida.append(actual)
    # una frase de una sola palabra se une a la vecina más cercana en el tiempo (si no hay pausa larga)
    unidas = []
    for f in salida:
        if unidas and len(f) == 1 and pal[f[0]]['t'] - pal[unidas[-1][-1]]['fin'] < 0.3 and len(unidas[-1]) < MAX_PALABRAS:
            unidas[-1] = unidas[-1] + f
        elif unidas and len(unidas[-1]) == 1 and pal[f[0]]['t'] - pal[unidas[-1][-1]]['fin'] < 0.3 and len(f) < MAX_PALABRAS:
            unidas[-1] = unidas[-1] + f
        else:
            unidas.append(list(f))
    return unidas


def puntajes(pal, frase, primera_del_video=False, A=AFINADO):
    """{índice: puntaje} de cada palabra de la frase como candidata a palabra grande."""
    sal = {}
    ultima_contenido = None
    for k in frase:
        if _es_contenido(pal[k]['plano']):
            ultima_contenido = k
    for pos, k in enumerate(frase):
        w = pal[k]['plano']
        if not _es_contenido(w):
            continue
        s = float(min(len(w), A['cap_len']))
        previa = pal[frase[pos - 1]]['plano'] if pos > 0 else ''
        siguiente = pal[frase[pos + 1]]['plano'] if pos + 1 < len(frase) else ''
        if previa in DET and not _es_contenido(siguiente):
            s += A['bonus_det']
        elif _es_contenido(siguiente):
            s -= A['pen_modifica']                 # va pegada a la palabra que sigue: suele ser adjetivo o verbo auxiliar, no la cabeza
        if k == ultima_contenido:
            s += A['bonus_ultima']
        if w.endswith(_FIN_PRET):
            s -= A['pen_pret']
        elif w.endswith(_FIN_VERBO):
            s -= A['pen_verbo']
        elif w.endswith(_FIN_ADJ):
            s += A['bonus_adj']
        elif w.endswith(_FIN_COND):
            s += A['bonus_cond']
        elif len(w) >= 5 and pal[k]['texto'].lower().endswith('ó'):
            s -= A['pen_verbo']
        if primera_del_video and pos == 0:
            s += A['bonus_gancho']
        sal[k] = s
    return sal


def elegir_mains(pal, frase, primera=False, forzados=None, A=AFINADO):
    """Índices (ordenados) de las palabras grandes de la frase."""
    if forzados is not None:
        return sorted(k for k in frase if k in forzados)
    pts = puntajes(pal, frase, primera, A)
    if not pts:
        return []
    ordenados = sorted(pts, key=lambda k: (-pts[k], -len(pal[k]['plano']), -k))
    if pts[ordenados[0]] < A['puntaje_min']:
        return []
    # frases de reacción (muy cortas, sin ninguna palabra con peso): se quedan sin palabra grande
    elegidas = [ordenados[0]]
    maximo = 1 if len(frase) <= 6 else (2 if len(frase) <= 11 else 3)
    for k in ordenados[1:]:
        if len(elegidas) >= maximo:
            break
        if pts[k] >= A['puntaje_2'] and all(abs(k - e) >= A['dist_mains'] for e in elegidas):
            elegidas.append(k)
    return sorted(elegidas)


def _debil(pal, k):
    return pal[k]['plano'] in STOP and len(pal[k]['plano']) <= 4


def _partir(pal, frase, mains, A=AFINADO, agrupadas=None):
    """Reparte la frase en bloques [[índices]] con a lo sumo dos palabras grandes (juntas solo si la frase es rápida) y MAX_PALABRAS palabras."""
    if not mains:
        trozos = [frase]
    else:
        trozos = []
        corte_ini = 0
        grupos = []
        for m in mains:
            if grupos and (pal[frase[-1]]['fin'] - pal[frase[0]]['t'] > A['combinar_s'] or len(frase) > MAX_PALABRAS or len(grupos[-1]) >= 2):
                grupos.append([m])
            elif grupos:
                grupos[-1].append(m)
            else:
                grupos.append([m])
        # fronteras entre grupos consecutivos: la mejor pausa/palabra no débil cerca del punto medio
        cortes = []
        for g0, g1 in zip(grupos, grupos[1:]):
            a, b = (agrupadas or {}).get(g0[-1], [g0[-1]])[-1], g1[0]
            candidatos = []
            for k in range(a, b):                       # corte DESPUÉS de la palabra k
                if _debil(pal, k):
                    continue
                pausa = pal[k + 1]['t'] - pal[k]['fin']
                post, pre = k - a, b - 1 - k
                candidatos.append((-(pausa >= A['pausa_coma']), abs(post - pre / 2.0), -pausa, k))
            cortes.append(min(candidatos)[3] if candidatos else (a + b) // 2)
        ini = 0
        for c in cortes:
            trozos.append([k for k in frase if ini <= k <= c])
            ini = c + 1
        trozos.append([k for k in frase if k >= ini])
    # trozos demasiado largos (frases sin palabra grande o muy cargadas): se parten por la mitad en una pausa
    final = []
    for t in trozos:
        pendiente = [t]
        while pendiente:
            u = pendiente.pop(0)
            if len(u) <= MAX_PALABRAS or len(u) < 4:
                final.append(u)
                continue
            mitad = len(u) // 2
            mejor = min(range(2, len(u) - 1), key=lambda j: (_debil(pal, u[j - 1]), -(pal[u[j]]['t'] - pal[u[j - 1]]['fin']), abs(j - mitad)))
            pendiente = [u[:mejor], u[mejor:]] + pendiente
    return [t for t in final if t]


def _negrita(pal, indices):
    """índice (dentro de `indices`) de la palabra en negrita de una línea pequeña, o None si no hay ninguna con peso (artículos, preposiciones…)."""
    contenido = [p for p, k in enumerate(indices) if _es_contenido(pal[k]['plano'])]
    if not contenido:
        return None
    if len(contenido) == 1:
        return contenido[0]
    # con varios candidatos: el segundo (ritmo fino · negrita · fino)
    return contenido[1]


def _pesos_linea(pal, indices, con_main, forzar=None):
    """El peso ('L' fina | 'B' negrita) de cada palabra de una línea pequeña, en orden.
    Sin ninguna palabra con peso: todo fino si hay palabra grande en el bloque y todo en negrita si es una frase suelta («a ver»).
    forzar {índice de pal: 'L'|'B'}: lo que el usuario marcó a mano en el editor (Abajo = negrita, Arriba = fina). Si la línea trae alguna en negrita
    forzada, SOLO esas van en negrita; si trae finas forzadas, la negrita automática se elige entre las demás; sin marcas, todo automático."""
    forzar = forzar or {}
    negritas = [p for p, k in enumerate(indices) if forzar.get(k) == 'B']
    finas = {p for p, k in enumerate(indices) if forzar.get(k) == 'L'}
    if negritas:
        pesos = ['B' if p in negritas else 'L' for p in range(len(indices))]
    else:
        if finas:
            contenido = [p for p, k in enumerate(indices) if p not in finas and _es_contenido(pal[k]['plano'])]
            b = None if not contenido else (contenido[0] if len(contenido) == 1 else contenido[1])
        else:
            b = _negrita(pal, indices)
        pesos = [('B' if p == b else 'L') if b is not None else ('L' if (con_main or finas) else 'B') for p in range(len(indices))]
    return pesos


def _tramos(pal, indices, con_main, A=AFINADO, forzar=None):
    """Una línea pequeña -> [(texto, 'L'|'B', t)]: las palabras seguidas del mismo peso se juntan en un tramo (los pesos, de _pesos_linea)."""
    if not indices:
        return []
    pesos = _pesos_linea(pal, indices, con_main, forzar)
    tramos = []
    for k, peso in zip(indices, pesos):
        t = pal[k]['t'] - A['adelanto']
        if tramos and tramos[-1][1] == peso:
            tramos[-1] = (tramos[-1][0] + ' ' + pal[k]['texto'], peso, tramos[-1][2])
        else:
            tramos.append((pal[k]['texto'], peso, t))
    return tramos


def _ancho_objetivo_main(texto, A=AFINADO):
    n = max(3, len(texto))
    return max(0.5, min(0.86, 0.55 + 0.035 * (n - 4)))


def _cabe(pack, n, texto, ancho_tl):
    """¿La palabra con el estilo n cabe en el ancho del comp SIN zoom? (si el texto es más ancho que el comp, Resolve lo recorta antes de ampliar)"""
    a = G.ancho_main(texto, n, pack, ancho_tl)
    if a is None:                              # sin medida (preset de Amro sin calibrar): solo palabras cortas
        return len(texto) <= 8
    return a <= AFINADO['cabe'] * ancho_tl


def _intencion(texto):
    """Estilos que pide el significado de la palabra grande (fuego → Fire, negación → Strike), o () si no pide ninguno."""
    plano = _plano(texto)
    if plano in {_plano(x) for x in _FUEGO}:
        return ESTILOS_FUEGO
    if plano in {_plano(x) for x in _NEGAR}:
        return ESTILOS_NEGACION
    return ()


def _estilo_para(pack, texto, previo, forzar=None, ancho_tl=1080, rotacion=None):
    """Estilo (variante del pack) de una palabra grande: el que pide su significado, o el siguiente de la rotación (`rotacion`: los de base o los
    acentos), siempre uno donde quepa."""
    n_est = max(G.datos_variantes(pack).keys() or [8])
    if forzar:
        return forzar
    rotacion = tuple(rotacion or ROTACION)
    resto = tuple(e for e in ROTACION if e not in rotacion)
    pedido = _intencion(texto)
    orden = [e for e in pedido if e <= n_est]
    i = (rotacion.index(previo) + 1) % len(rotacion) if previo in rotacion else 0
    orden += [rotacion[(i + paso) % len(rotacion)] for paso in range(len(rotacion))] + list(resto)
    orden = [e for e in orden if e <= n_est and e != previo] or [1]
    for e in orden:
        if _cabe(pack, e, texto, ancho_tl):
            return e
    # ninguna cabe (palabra larguísima): la de menor ancho natural
    return min(orden, key=lambda e: G.ancho_main(texto, e, pack, ancho_tl) or 0)


def _alto_main(texto, w, ancho_tl=1080, A=AFINADO):
    """Alto aproximado (fracción del cuadro, 9:16 = 1920 px) de la tinta de la palabra grande con ancho w (medido en los renders: ~1,45 veces ancho/letras)."""
    return max(0.055, min(0.10, 1.45 * w * ancho_tl / (max(5, len(texto)) * 1920.0)))


def _agrupar(ms):
    """Varias palabras seguidas pintadas como grandes forman UNA palabra grande de varias palabras. -> (cabezas, {cabeza: [índices]})"""
    cabezas, grupos = [], {}
    for k in sorted(ms):
        if cabezas and grupos[cabezas[-1]][-1] == k - 1:
            grupos[cabezas[-1]].append(k)
        else:
            cabezas.append(k)
            grupos[k] = [k]
    return cabezas, grupos


def planificar(palabras, idioma='es', pack='Referencia', ancho_tl=1080, ancla='medio', mains=None, estilos=None, fin_video=None, pesos=None, estilos_palabra=None, variar_barrido=True):
    """palabras [{'word','start','end'}] -> (bloques para guion_captions.construir_cues, plan para depurar).

    mains: palabras (texto) o índices que se fuerzan como palabras grandes (None = las elige el planificador); varias seguidas = una sola palabra grande.
    estilos: {índice de bloque: n de estilo} para forzar la variante de un bloque.
    pesos: {índice de palabra: 'L'|'B'} lo que el usuario marcó a mano en el editor: fina (Arriba) o negrita (Abajo); el resto, automático.
    estilos_palabra: {índice de palabra: n}: el estilo que el usuario eligió para el bloque de esa palabra (manda en TODAS las grandes del bloque).
    variar_barrido: alterna la forma del barrido de luz de las palabras grandes Luxe (original → Screen → Sólido, ver BARRIDOS) si el pack trae esas variantes; lo que el usuario fijó a mano no se toca.
    ancla: 'medio' | 'alto' | 'bajo' | 'alterna' (el centro vertical de la pila).
    Cada elemento del plan lleva 'orig' (los índices de las palabras que se entregaron y quedaron en el bloque) para que el editor sepa qué palabra va en qué bloque.
    """
    A = AFINADO
    pal = _preparar(palabras)
    if not pal:
        return [], []
    forzar_peso, forzar_estilo = {}, {}
    for k in pal:
        for o in k['orig']:
            if pesos and o in pesos and pesos[o] in ('L', 'B'):
                forzar_peso[k['i']] = pesos[o]
            if estilos_palabra and estilos_palabra.get(o):
                forzar_estilo[k['i']] = int(estilos_palabra[o])
    forzados = None
    if mains:
        forzados = set()
        pedidos = {_plano(str(m)) for m in mains if not isinstance(m, int)}
        forzados |= {k['i'] for k in pal if k['plano'] in pedidos}
        idx_pedidos = {int(m) for m in mains if isinstance(m, int)}              # índices de la lista que se entregó (no de `pal`, que quita vacías y tartamudeos)
        forzados |= {k['i'] for k in pal if idx_pedidos & set(k['orig'])}
    bloques, plan = [], []
    ult_base = ult_acento = base_oracion = None
    n_barridos = 0
    try:
        con_variantes = set(G.datos_variantes(pack).keys())
    except Exception:
        con_variantes = set()
    for n_frase, frase in enumerate(frases(pal, A)):
        ms = elegir_mains(pal, frase, primera=(n_frase == 0), forzados=forzados, A=A)
        cabezas, grupos = _agrupar(ms)
        miembros = {k for g in grupos.values() for k in g[1:]}
        for trozo in _partir(pal, frase, cabezas, A, grupos):
            plan.append({'frase': n_frase, 'palabras': trozo, 'mains': [k for k in trozo if k in cabezas], 'grupos': grupos, 'miembros': miembros,
                         'orig': sorted(o for k in trozo for o in pal[k]['orig'])})
    # ORACIONES: un bloque abre oración nueva si lo anterior acabó en signo fuerte o con una pausa (los signos a veces se pierden por el camino)
    oraciones, o = [], -1
    for n, b in enumerate(plan):
        k0 = b['palabras'][0]
        previa = pal[k0 - 1] if k0 > 0 else None
        if previa is None or (bool(previa['signo']) and previa['signo'] in _FUERTE) or pal[k0]['t'] - previa['fin'] >= A['pausa_oracion']:
            o += 1
        oraciones.append(o)
    mains_de_oracion, ultimo_con_main = {}, {}
    for n, b in enumerate(plan):
        if b['mains']:
            mains_de_oracion[oraciones[n]] = mains_de_oracion.get(oraciones[n], 0) + len(b['mains'])
            ultimo_con_main[oraciones[n]] = n
    # tiempos y composición de cada bloque
    for n, b in enumerate(plan):
        idx = b['palabras']
        t0 = pal[idx[0]]['t'] - A['adelanto']
        sig_t0 = (pal[plan[n + 1]['palabras'][0]]['t'] - A['adelanto']) if n + 1 < len(plan) else None
        ultimo_fin = pal[idx[-1]]['fin']
        t1 = ultimo_fin + A['hold']
        if sig_t0 is not None:
            t1 = min(t1, sig_t0 - A['gap_minimo'])
        elif fin_video:
            t1 = max(t1, min(float(fin_video), ultimo_fin + 1.0))
        t1 = max(t1, t0 + A['min_bloque'])
        if sig_t0 is not None and t1 > sig_t0 - 0.02:
            t1 = max(t0 + 0.3, sig_t0 - 0.02)
        b['t0'], b['t1'] = round(max(0.0, t0), 3), round(t1, 3)
        # segmentos en orden de lectura: [S] M [S] (M) [S]
        segs, cur = [], []
        for k in idx:
            if k in b['mains']:
                if cur:
                    segs.append(('S', cur))
                    cur = []
                segs.append(('M', b['grupos'].get(k, [k])))
            elif k not in b['miembros']:
                cur.append(k)
        if cur:
            segs.append(('S', cur))

        def texto_de(ks):
            t = ' '.join(pal[m]['texto'] for m in ks)
            return t[:1].upper() + t[1:]
        # estilo de cada palabra grande. Como en la referencia, los bloques de una misma ORACIÓN comparten estilo (5·5·5, 2·2) y cada oración
        # nueva estrena el siguiente de los de base (Luxe); la palabra gancho del primer bloque lleva el suyo; el REMATE de una oración con
        # varias palabras grandes (la última) lleva un acento de Amro (pastilla, subrayado) y fuego/negación mandan por significado.
        if n == 0 or oraciones[n] != oraciones[n - 1]:
            base_oracion = None
        n_m = sum(1 for tipo, _ks in segs if tipo == 'M')
        est = []
        # el estilo que el usuario eligió para este bloque (por número de bloque o por la palabra donde lo dejó) manda en TODAS sus palabras grandes
        forzado_bloque = (estilos or {}).get(n) or next((forzar_estilo[k] for k in idx if k in forzar_estilo), None)
        for tipo, ks in segs:
            if tipo != 'M':
                continue
            texto = texto_de(ks)
            forzado = forzado_bloque
            remate = (oraciones[n] > 0 and n == ultimo_con_main[oraciones[n]] and len(est) == n_m - 1 and mains_de_oracion[oraciones[n]] >= 2)
            if forzado:
                e = forzado
            elif _intencion(texto):
                e = _estilo_para(pack, texto, ult_base, None, ancho_tl, ESTILOS_BASE)          # el significado manda (fuego, negación)
            elif remate:
                e = ult_acento = _estilo_para(pack, texto, ult_acento, None, ancho_tl, ESTILOS_ACENTO)
            elif not est and base_oracion is not None and _cabe(pack, base_oracion, texto, ancho_tl):
                e = base_oracion                                   # el bloque sigue la oración: mismo estilo que el anterior
            else:
                e = ult_base = _estilo_para(pack, texto, ult_base, None, ancho_tl, ESTILOS_BASE)
                if not est and base_oracion is None and n > 0:
                    base_oracion = e                               # el estilo con el que arranca la oración (el gancho del bloque 0 no cuenta)
            if variar_barrido and not forzado and e in BARRIDOS and all(v in con_variantes for v in BARRIDOS[e]):
                est.append(BARRIDOS[e][n_barridos % 3])        # la forma del barrido va rotando; el estilo BASE (e) sigue siendo el que cuenta para la oración
                n_barridos += 1
            else:
                est.append(e)
        b['estilos'] = est
        # alturas
        alturas, anchos = [], {}
        for j, (tipo, ks) in enumerate(segs):
            if tipo == 'M':
                anchos[j] = _ancho_objetivo_main(texto_de(ks))
                alturas.append(_alto_main(texto_de(ks), anchos[j], ancho_tl))
            else:
                alturas.append(A['alto_linea'])
        total = sum(alturas) + A['hueco'] * (len(alturas) - 1)
        yc = ANCLAS.get(ancla, ANCLAS['medio'])
        if ancla == 'alterna':
            yc = (ANCLAS['medio'], ANCLAS['medio'], ANCLAS['alto'])[n % 3]
        top = max(0.10, min(0.90 - total, yc - total / 2.0))
        lineas, y, m_i = [], top, 0
        for j, ((tipo, ks), h) in enumerate(zip(segs, alturas)):
            centro = round(y + h / 2.0, 4)
            y += h + A['hueco']
            if tipo == 'M':
                lineas.append(('M', [(texto_de(ks), round(pal[ks[0]]['t'] - A['adelanto'], 3), est[m_i])], 0.5, centro, round(anchos[j], 3)))
                m_i += 1
            else:
                tr = _tramos(pal, ks, bool(b['mains']), A, forzar_peso)
                for k_p, peso_p in zip(ks, _pesos_linea(pal, ks, bool(b['mains']), forzar_peso)):
                    for o in pal[k_p]['orig']:
                        b.setdefault('pesos', {})[o] = peso_p          # para que el editor pinte lo que el planificador decide solo (negrita = «Abajo»)
                natural = sum(G.ancho_px(t, G.FINA if p == 'L' else G.NEGRITA, G.TAM_PEQUENA, ancho_tl) for t, p, _ in tr) / float(ancho_tl)
                # una línea pequeña más ancha que el cuadro se reduce hasta 0,92 del ancho
                lineas.append(('S', [(t, p, round(tt, 3)) for t, p, tt in tr], 0.5, centro, 0.92 if natural * G.AFINADO['tinta_pequena'] > 0.92 else None))
        b['estilo_bloque'] = est[0] if est else None
        b['grandes'] = sorted(o for tipo, ks in segs if tipo == 'M' for k_g in ks for o in pal[k_g]['orig'])       # las palabras que quedaron GRANDES (índices entregados)
        # la caja de la pila (fracción del alto, desde arriba): el emoji del bloque se coloca encima o debajo de ella
        bloques.append({'t0': b['t0'], 't1': b['t1'], 'estilo': est[0] if est else None, 'lineas': lineas, 'caja': (round(top, 4), round(top + total, 4))})
    return bloques, plan


def cues_de(palabras, idioma='es', pack='Referencia', ancho_tl=1080, **kw):
    """Atajo: planifica y deja los bloques listos para el JSON de place_guion_track. El pack «Tema4» (Tema 4) arma sus bloques con su propio planificador (tema4_planificador.py:
    recuadro, tres tamaños de letra, palabras que aparecen una a una) pero usa el mismo colocador de Resolve."""
    if pack in ('Tema4', 'Tema5', 'Tema6'):                   # el Tema 5 usa los bloques del Tema 4 (sus captions Text+ son el respaldo de los de Remotion)
        import tema4_planificador
        return tema4_planificador.cues_de(palabras, idioma, pack, ancho_tl, **kw)
    bloques, plan = planificar(palabras, idioma, pack, ancho_tl, **kw)
    return G.construir_cues(bloques, pack, ancho_tl), plan


# ---------------------------------------------------------------------------------------------------------------------------------------------
# Comparación con la referencia
# ---------------------------------------------------------------------------------------------------------------------------------------------
def evaluar(palabras=None, **kw):
    """Compara el plan con guion_referencia.BLOQUES. Devuelve un dict con aciertos y la lista de diferencias (para mirarlas).
    Sin `palabras` usa las de la referencia (guion_referencia.PALABRAS)."""
    import guion_referencia as R
    if palabras is None:
        palabras = R.palabras_de_la_referencia()
    kw.setdefault('variar_barrido', False)                  # la referencia usa los estilos 1-8: las variantes de barrido (9-16) no cuentan en la comparación
    bloques, plan = planificar(palabras, **kw)
    ref = []
    for b in R.BLOQUES:
        mains = [p[0] for l in b['lineas'] if l[0] == 'M' for p in l[1]]
        ref.append({'t0': b['t0'], 't1': b['t1'], 'mains': [_plano(m) for m in mains], 'estilo': b.get('estilo')})
    mios = []
    for b, p in zip(bloques, plan):
        mains = [m[0] for l in b['lineas'] if l[0] == 'M' for m in l[1]]
        mios.append({'t0': b['t0'], 't1': b['t1'], 'mains': [_plano(m) for m in mains], 'estilo': b.get('estilo')})
    ref_mains = {m for r in ref for m in r['mains']}
    mis_mains = {m for r in mios for m in r['mains']}
    # los textos de la referencia se corrigieron a mano (guapísimo→guapísima, barriches→berrinches): se compara por prefijo
    def casa(a, B):
        return any(a == b or (len(a) >= 5 and len(b) >= 5 and a[:5] == b[:5]) for b in B)
    ok_mains = sum(1 for m in ref_mains if casa(m, mis_mains))
    sobran = [m for m in mis_mains if not casa(m, ref_mains)]
    inicios_ref = [r['t0'] for r in ref]
    inicios_mios = [r['t0'] for r in mios]
    ok_cortes = sum(1 for t in inicios_ref if any(abs(t - u) <= 0.3 for u in inicios_mios))
    # estilo de los bloques que la referencia pinta con uno solo (el de «Fiesta/SHOW» lleva dos y no cuenta)
    est_total = est_ok = 0
    for r in ref:
        if not r['estilo']:
            continue
        vecino = [m for m in mios if abs(m['t0'] - r['t0']) <= 0.4 and m['estilo']]
        if vecino:
            est_total += 1
            est_ok += int(vecino[0]['estilo'] == r['estilo'])
    return {'mains_ref': len(ref_mains), 'mains_ok': ok_mains, 'mains_de_mas': sobran, 'bloques_ref': len(ref), 'bloques_mios': len(mios),
            'cortes_ok': ok_cortes, 'estilos_ok': est_ok, 'estilos_total': est_total, 'mios': mios, 'ref': ref}
