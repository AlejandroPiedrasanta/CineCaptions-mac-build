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
ESTILOS_BASE = (1, 2, 5)                     # (v5.48: sin el 4, «Moderno blanco», eliminado) Luxe: el estilo «de fondo» de cada oración (pack «Referencia»: en el orden en que los estrena la referencia)
ESTILOS_ACENTO = (3, 8)                      # presets de Amro sueltos (pastilla, subrayado): el REMATE de la oración; fuego (6) y negación (7) van por significado
ROTACION = ESTILOS_BASE + ESTILOS_ACENTO + (6, 7)
ESTILOS_FUEGO = (6,)
# v5.5: los estilos Luxe de base (1, 2, 4, 5) tienen tres formas de BARRIDO DE LUZ en el pack: el original (sutil), «Screen» (una banda de luz de color que se suma) y «Sólido» (una banda opaca).
# {estilo base: (original, screen, sólido)}; las palabras grandes los van alternando para que el barrido (y su color) no se repita. Sólo cuando el pack trae esas variantes (9-16).
BARRIDOS = {1: (1, 9, 13), 2: (2, 10, 14), 5: (5, 12, 16)}            # (v5.48: «Moderno blanco» 4/11/15 eliminado del pack)
ESTILOS_NEGACION = (7,)
# v5.48 (pedido: «usa Luxe Count para números y si habla de dinero pon el signo de la moneda»): las cifras van GRANDES con la variante 17
# (macro Luxe Count: cuenta de 0 a la cifra; el prefijo de moneda, el «%» y los decimales salen del texto que le escribe el planificador)
VARIANTE_COUNT = 17
_NUMEROS = {'dos': '2', 'tres': '3', 'cuatro': '4', 'cinco': '5', 'seis': '6', 'siete': '7', 'ocho': '8', 'nueve': '9', 'diez': '10', 'once': '11',
            'doce': '12', 'quince': '15', 'veinte': '20', 'treinta': '30', 'cuarenta': '40', 'cincuenta': '50', 'cien': '100', 'mil': '1000',
            'two': '2', 'three': '3', 'four': '4', 'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10', 'twenty': '20',
            'hundred': '100', 'thousand': '1000'}
_MONEDAS = {'dolar': '$', 'dolares': '$', 'peso': '$', 'pesos': '$', 'quetzal': 'Q', 'quetzales': 'Q', 'euro': '€', 'euros': '€', 'libra': '£', 'libras': '£',
            'dollar': '$', 'dollars': '$', 'bucks': '$'}
ESTILOS_LINEA3_CENTRADA = (8,)               # v5.48 (pedido): con el subrayado (8) la línea de debajo va centrada bajo la grande, no a la derecha
# v5.5.8: con las líneas juntas (hueco 0,004) las palabras grandes en letra editorial / de pincel (2 rosa, 5 azul y sus barridos) pisaban la
# línea de al lado: sus trazos suben y bajan más que la caja medida. Llevan un poco de aire arriba y abajo.
ESTILOS_EDITORIAL = (2, 5, 10, 12, 14, 16)
AIRE_EDITORIAL = 0.012
# v5.48 (el usuario: «muy rápido y no están fluidos»; medido contra REFERENCIA.mp4 / ref_exacta): cada palabra entra cuando se dice (la referencia
# va ~0,08 s DETRÁS de la voz), la última de cada bloque se ve al menos 'respiro' s (el siguiente espera hasta 'espera_max' s; ver _respiro) y entre
# bloque y bloque queda un instante vacío ('gap_minimo'; en la referencia 0,15-0,25 s). Las grandes no pasan de 'zoom_max' (la referencia: 0,9-1,3).
AFINADO = {'adelanto': 0.0, 'respiro': 0.55, 'espera_max': 0.35, 'zoom_max': 1.3, 'cortos_entre': 2, 'complejo_max': 4, 'complejo_s': 3.2, 'max_linea': 4, 'zoom_max_cifra': 1.7, 'bloque_min': 1.2,
           # v5.48 (pedido: «más junto en general y el principal un poco más grande»): la grande = 1,1 × el ancho de su línea pequeña (y ≥1,1 × su
           # tamaño natural); alturas estimadas más ceñidas a la tinta ('k_alto' 1,45 -> 1,3; 'alto_linea' 0,036 -> 0,031)
           'grande_linea': 1.1, 'grande_min': 1.1, 'k_alto': 1.35, 'k_alto_sans': 1.7, 'hold': 0.22, 'min_bloque': 0.7, 'gap_minimo': 0.15, 'puntaje_min': 8.0, 'puntaje_2': 9.0, 'dist_mains': 4,
           'pausa_frase': 0.45, 'pausa_coma': 0.12, 'combinar_s': 2.0, 'cap_len': 10, 'bonus_det': 4.0, 'bonus_ultima': 4.0, 'bonus_gancho': 8.0,
           'pen_verbo': 3.0, 'pen_pret': 6.0, 'pen_modifica': 2.0, 'bonus_adj': 3.0, 'bonus_cond': 5.0, 'hueco': 0.006, 'cabe': 0.96, 'alto_linea': 0.031,
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


def _complejos(plan, pal, A=AFINADO):
    """v5.48 (pedido: «bloques más complejos de tres líneas, la principal en medio, y bloques cortos»): alterna un bloque de TRES líneas
    (pequeña · PRINCIPAL · pequeña) con bloques cortos. Un bloque que acaba en su palabra grande se lleva las primeras palabras pequeñas del
    siguiente (hasta 'complejo_max' y sin pausa larga entre medias): queda pequeña · grande · pequeña y el siguiente, más corto. Tras un bloque de
    tres líneas vienen al menos 'cortos_entre' bloques cortos."""
    cortos = A['cortos_entre']                     # el primero puede ser de tres líneas
    for n, b in enumerate(plan):
        idx = b['palabras']
        tres = bool(b['mains']) and idx[0] not in b['mains'] and idx[-1] not in b['mains'] and idx[-1] not in b['miembros']
        if tres:
            cortos = 0
            continue
        sig = plan[n + 1] if n + 1 < len(plan) else None
        ultima = max(b['mains'] + [k for g in b['mains'] for k in b['grupos'].get(g, [g])]) if b['mains'] else None
        if (cortos < A['cortos_entre'] or not b['mains'] or idx[0] in b['mains'] or ultima != idx[-1] or not sig or not sig['mains']):
            cortos += 1
            continue
        tomar = []
        for k in sig['palabras']:
            if k in sig['mains'] or k in sig['miembros'] or len(tomar) >= A['complejo_max']:
                break
            antes = tomar[-1] if tomar else idx[-1]
            if pal[k]['t'] - pal[antes]['fin'] > A['pausa_frase'] or pal[k]['fin'] - pal[idx[0]]['t'] > A['complejo_s']:
                break
            tomar.append(k)
        while tomar and _debil(pal, tomar[-1]):
            tomar.pop()                            # no se corta tras «de», «la», «que»… (se quedan con su palabra en el siguiente)
        if len(tomar) < 2 or len(tomar) >= len(sig['palabras']):     # (la línea de debajo de la grande lleva al menos 2 palabras)
            cortos += 1
            continue
        b['palabras'] = idx + tomar
        sig['palabras'] = [k for k in sig['palabras'] if k not in tomar]
        b['orig'] = sorted(o for k in b['palabras'] for o in pal[k]['orig'])
        sig['orig'] = sorted(o for k in sig['palabras'] for o in pal[k]['orig'])
        cortos = 0
    return [b for b in plan if b['palabras']]


def _corte(pal, ks, minimo, maximo, medio=False, fin=None):
    """Cuántas palabras de `ks` van en el primer trozo (entre minimo y maximo): nunca tras «de», «la», «y»… si se puede, mejor donde hay pausa y
    con los dos trozos lo más parejos: en palabras (`medio`) o en TIEMPO en pantalla (el segundo dura hasta `fin`, p. ej. el final de su grande),
    así ninguno de los dos queda en un bloque fugaz."""
    opciones = list(range(max(1, minimo), min(len(ks) - 1, maximo) + 1)) or [max(1, min(len(ks) - 1, maximo))]
    hasta = fin if fin is not None else pal[ks[-1]]['fin']
    def nota(c):
        pausa = pal[ks[c]]['t'] - pal[ks[c - 1]]['fin']
        parejo = -abs(c - len(ks) / 2.0) if medio else min(pal[ks[c - 1]]['fin'] - pal[ks[0]]['t'], hasta - pal[ks[c]]['t'])
        return (not _debil(pal, ks[c - 1]), parejo + (0.25 if pausa >= 0.15 else 0.0))
    return max(opciones, key=nota)


def _reglas_lineas(plan, pal, A=AFINADO):
    """v5.48 (pedido del usuario): ninguna línea pequeña pasa de A['max_linea'] (4) palabras; la línea de DEBAJO de la grande nunca lleva una sola
    palabra ni acaba en «de», «del», «la», «y»… (esas pasan al bloque siguiente, con la palabra a la que acompañan). Si lo que va antes de la grande
    no cabe, se corta por un sitio natural («La Unión Europea» | «trae a / Quetzaltenango») y lo de delante forma su propio bloque. Un bloque sin
    grande de 5 a 8 palabras va en DOS líneas del mismo bloque (lo reparte _lineas_pequenas), no en dos bloques fugaces."""
    MAX = A['max_linea']

    def partes(b):
        if not b['mains']:
            return b['palabras'], [], []
        m0 = min(b['mains'])
        fin = max(k for g in b['mains'] for k in b['grupos'].get(g, [g]))
        return [k for k in b['palabras'] if k < m0], [k for k in b['palabras'] if m0 <= k <= fin], [k for k in b['palabras'] if k > fin]

    def nuevo(b, ks):
        return dict(b, palabras=ks, mains=[], orig=sorted(o for k in ks for o in pal[k]['orig']))

    def fijar(b, ks):
        b['palabras'] = ks
        b['orig'] = sorted(o for k in ks for o in pal[k]['orig'])

    salida, cola = [], list(plan)
    while cola:
        b = cola.pop(0)
        antes, medio, despues = partes(b)
        if b['mains'] and despues:
            # la línea de debajo no acaba en «de/la/y…» ni lleva una sola palabra: lo que sobra va al principio del bloque siguiente
            pasa = []
            junto = (bool(cola) and pal[cola[0]['palabras'][0]]['t'] - pal[despues[-1]]['fin'] < A['pausa_frase']
                     and not (pal[despues[-1]]['signo'] and pal[despues[-1]]['signo'] in _FUERTE))       # (nunca por encima de un fin de frase)
            while despues and (_debil(pal, despues[-1]) or len(despues) == 1) and junto:
                pasa.insert(0, despues.pop())
            if len(despues) == 1 and not junto:             # sin bloque siguiente pegado: esa palabra va sola en su bloque
                cola.insert(0, nuevo(b, despues))
                despues = []
            if pasa:
                fijar(cola[0], pasa + cola[0]['palabras'])
            fijar(b, antes + medio + despues)
        if not b['mains'] and len(antes) > 2 * MAX:                 # sin grande y larguísimo: en dos bloques (cada uno, hasta dos líneas)
            corte = _corte(pal, antes, len(antes) - 2 * MAX, 2 * MAX, medio=True)
            fijar(b, antes[corte:])
            cola[:0] = [nuevo(b, antes[:corte]), b]
            continue
        if b['mains'] and len(antes) > MAX:                         # lo que no cabe delante de la grande: su propio bloque antes
            sobra = _corte(pal, antes, max(2, len(antes) - MAX), len(antes) - 2, fin=pal[medio[-1]]['fin'] + A['respiro'])
            fijar(b, antes[sobra:] + medio + despues)
            cola[:0] = [nuevo(b, antes[:sobra]), b]
            continue
        if b['mains'] and len(despues) > MAX:                       # lo que no cabe debajo: su propio bloque después
            queda = _corte(pal, despues, 2, min(MAX, len(despues) - 2))
            cola.insert(0, nuevo(b, despues[queda:]))
            fijar(b, antes + medio + despues[:queda])
        salida.append(b)
    return [b for b in salida if b['palabras']]


def _juntar_cortos(plan, pal, A=AFINADO):
    """v5.48 (pedido: «se ve muy rápido»): un bloque que se vería menos de A['bloque_min'] s se junta con su vecino de la misma frase, como una
    línea más, si las reglas lo permiten (una sola grande por bloque, ≤3 líneas, ≤4 palabras por línea, la línea de debajo de la grande con ≥2
    palabras y sin acabar en «de/la/y…»): «Se pasaron» + «me hicieron el día» -> un bloque de dos líneas."""
    MAX = A['max_linea']

    def partes(b):
        if not b['mains']:
            return b['palabras'], [], []
        m0 = min(b['mains'])
        fin = max(k for g in b['mains'] for k in b['grupos'].get(g, [g]))
        return [k for k in b['palabras'] if k < m0], [k for k in b['palabras'] if m0 <= k <= fin], [k for k in b['palabras'] if k > fin]

    def lineas(b):
        antes, medio, despues = partes(b)
        if not b['mains']:
            return 1 if len(antes) <= MAX else 2
        return (len(antes) + MAX - 1) // MAX + 1 + (1 if despues else 0)

    def dura(b):
        return pal[b['palabras'][-1]]['fin'] - pal[b['palabras'][0]]['t'] + A['respiro']

    def seguidos(a, b):
        ult = pal[a['palabras'][-1]]
        return pal[b['palabras'][0]]['t'] - ult['fin'] < A['pausa_frase'] and not (ult['signo'] and ult['signo'] in _FUERTE)

    def juntar(a, b):
        ks = a['palabras'] + b['palabras']
        return dict(b if b['mains'] else a, palabras=ks, mains=a['mains'] + b['mains'], orig=sorted(o for k in ks for o in pal[k]['orig']))

    i = 0
    while i + 1 < len(plan):
        a, b = plan[i], plan[i + 1]
        corto = min(dura(a), dura(b)) < A['bloque_min']
        if not corto or not seguidos(a, b) or (a['mains'] and b['mains']) or dura(juntar(a, b)) > A['complejo_s'] + 0.6:
            i += 1
            continue
        nuevo = juntar(a, b)
        antes, medio, despues = partes(nuevo)
        ok = lineas(nuevo) <= 3 and (not nuevo['mains'] or len(antes) <= 2 * MAX)
        if nuevo['mains'] and despues:
            ok = ok and len(despues) >= 2 and len(despues) <= MAX and not _debil(pal, despues[-1])
        if not nuevo['mains']:
            ok = ok and len(antes) <= 2 * MAX
        if ok:
            plan[i:i + 2] = [nuevo]
            i = max(0, i - 1)                           # (el bloque nuevo puede juntarse otra vez con el de antes)
        else:
            i += 1
    return plan


def _lineas_pequenas(pal, segs, A=AFINADO):
    """Una línea pequeña de más de A['max_linea'] palabras (bloque sin grande) se parte en dos líneas por un sitio natural."""
    salida = []
    for tipo, ks in segs:
        if tipo == 'S' and len(ks) > A['max_linea']:
            c = _corte(pal, ks, len(ks) - A['max_linea'], A['max_linea'], medio=True)
            salida += [('S', ks[:c]), ('S', ks[c:])]
        else:
            salida.append((tipo, ks))
    return salida


def _ancho_linea(pal, ks, A, forzar, ancho_tl):
    """Ancho de tinta (fracción del ancho) de una línea pequeña con sus pesos."""
    tr = _tramos(pal, ks, True, A, forzar)
    return (sum(G.ancho_px(t, G.FINA if p == 'L' else G.NEGRITA, G.TAM_PEQUENA, ancho_tl) for t, p, _ in tr)
            + G.ancho_px(' ', G.FINA, G.TAM_PEQUENA, ancho_tl) * G.AFINADO['espacio'] * (len(tr) - 1)) * G.AFINADO['tinta_pequena'] / float(ancho_tl)


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
        if not finas:
            pesos = _ritmo_pesos(pal, indices, pesos)
    return pesos


MAX_FINAS, MAX_NEGRITAS = 3, 2


def _ritmo_pesos(pal, indices, pesos):
    """v5.48 (pedido: «jamás 4 palabras en light, tiene que tener un bold; máximo 2 en bold y máximo 3 en light»): toda línea de 2+ palabras lleva
    al menos una negrita, nunca más de MAX_FINAS finas seguidas ni más de MAX_NEGRITAS negritas seguidas."""
    pesos = list(pesos)
    n = len(pesos)

    def valor(p):                                  # la mejor candidata a negrita: palabra con contenido, larga
        return (_es_contenido(pal[indices[p]]['plano']), len(pal[indices[p]]['plano']))

    if n >= 2 and 'B' not in pesos:
        pesos[max(range(n), key=valor)] = 'B'
    p = 0
    while p < n:                                   # tramos de finas demasiado largos: una negrita dentro (sin pegarla a otra negrita si se puede)
        q = p
        while q < n and pesos[q] == pesos[p]:
            q += 1
        if pesos[p] == 'L' and q - p > MAX_FINAS:
            cand = [r for r in range(p + 1, q - 1)] or list(range(p, q))
            pesos[max(cand, key=valor)] = 'B'
            p = 0
            continue
        if pesos[p] == 'B' and q - p > MAX_NEGRITAS:
            menos = sorted(range(p, q), key=valor)[:q - p - MAX_NEGRITAS]
            for r in menos:
                pesos[r] = 'L'
            p = 0
            continue
        p = q
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


def cifras(pal):
    """{índice: (texto para el Luxe Count, [índices de la cantidad])} de las palabras que son una cantidad: '430,000' · '$430,000' · '50%' · '9.99'
    · 'tres' -> '3'. «mil» / «millones» detrás van con su número («430 mil» -> '430,000', «dos millones» -> '2,000,000'). Si va pegada a una moneda
    («430 mil dólares», «500 quetzales») o ya la trae, lleva su signo delante. «1.500» (punto de miles) -> «1,500». («uno/una» no: casi siempre
    son artículos.)"""
    salida, k = {}, 0
    while k < len(pal):
        t = pal[k]['texto'].strip().strip(',;:!?¡¿').rstrip('.')
        signo = t[0] if t[:1] in '$€£' else ''
        cuerpo = t[len(signo):]
        pct = cuerpo.endswith('%')
        cuerpo = cuerpo.rstrip('%')
        if re.fullmatch(r'\d{1,3}(\.\d{3})+', cuerpo):
            cuerpo = cuerpo.replace('.', ',')
        if not signo and not pct and re.fullmatch(r'(19|20)\d\d', cuerpo):
            k += 1                                        # un año («en 2026») no es una cantidad: no cuenta ni lleva comas
            continue
        if re.fullmatch(r'\d[\d,]*(\.\d{1,2})?', cuerpo):
            valor = float(cuerpo.replace(',', ''))
        elif not signo and not pct and pal[k]['plano'] in _NUMEROS:
            valor = float(_NUMEROS[pal[k]['plano']].replace(',', ''))
        else:
            k += 1
            continue
        grupo = [k]
        if not pct and k + 1 < len(pal) and pal[k + 1]['plano'] in ('mil', 'millones', 'millon', 'thousand', 'million', 'millions'):
            valor *= 1000 if pal[k + 1]['plano'] in ('mil', 'thousand') else 1000000
            grupo.append(k + 1)
        if not signo:
            for j in (grupo[-1] + 1, grupo[-1] + 2):          # «430 dólares», «500 millones de pesos»
                if j < len(pal) and pal[j]['plano'] in _MONEDAS:
                    signo = _MONEDAS[pal[j]['plano']]
                    grupo += list(range(grupo[-1] + 1, j + 1))   # la palabra de la moneda (y el «de») ya la dice el signo: va dentro de la cifra
                    break
                if j < len(pal) and pal[j]['plano'] != 'de':
                    break
        decimales = len(cuerpo.split('.')[1]) if '.' in cuerpo and valor == float(cuerpo.replace(',', '')) else 0
        salida[k] = (signo + f'{valor:,.{decimales}f}' + ('%' if pct else ''), grupo)
        k = grupo[-1] + 1
    return salida


def _estilo_para(pack, texto, previo, forzar=None, ancho_tl=1080, rotacion=None):
    """Estilo (variante del pack) de una palabra grande: el que pide su significado, o el siguiente de la rotación (`rotacion`: los de base o los
    acentos), siempre uno donde quepa."""
    hay = set(G.datos_variantes(pack).keys()) or set(range(1, 9))       # (v5.48: el pack puede tener huecos: 4, 11, 15 eliminados)
    if forzar:
        return forzar
    rotacion = tuple(rotacion or ROTACION)
    # (v5.48: el tachado y el fuego solo los pide el significado: antes, si ninguna otra cabía, «Quetzaltenango» salía tachado en rojo)
    resto = tuple(e for e in ROTACION if e not in rotacion and e not in ESTILOS_NEGACION + ESTILOS_FUEGO)
    pedido = _intencion(texto)
    orden = [e for e in pedido if e in hay]
    i = (rotacion.index(previo) + 1) % len(rotacion) if previo in rotacion else 0
    orden += [rotacion[(i + paso) % len(rotacion)] for paso in range(len(rotacion))] + list(resto)
    orden = [e for e in orden if e in hay and e != previo] or [1]
    for e in orden:
        if _cabe(pack, e, texto, ancho_tl):
            return e
    # ninguna cabe (palabra larguísima): la de menor ancho natural
    return min(orden, key=lambda e: G.ancho_main(texto, e, pack, ancho_tl) or 0)


def _alto_main(texto, w, ancho_tl=1080, A=AFINADO, estilo=None):
    """Alto aproximado (fracción del cuadro, 9:16 = 1920 px) de la tinta de la palabra grande con ancho w: k × ancho/letras. v5.48, medido en Resolve:
    las serif cursivas (editoriales) ~1,35; Poppins / Inter (Impacto, Moderno, Amro, Count) son más altas para su ancho: ~1,7."""
    k = A['k_alto'] if estilo in ESTILOS_EDITORIAL else A['k_alto_sans']
    return max(0.05, min(0.16, k * w * ancho_tl / (max(5, len(texto)) * 1920.0)))


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
    numeros = cifras(pal) if VARIANTE_COUNT in con_variantes else {}
    for n_frase, frase in enumerate(frases(pal, A)):
        ms = elegir_mains(pal, frase, primera=(n_frase == 0), forzados=forzados, A=A)
        if forzados is None and numeros:
            # las cifras van grandes (Luxe Count); la grande que tuviera pegada deja de serlo (formarían un grupo que ya no es una cifra)
            nums = [x for k in frase if k in numeros for x in numeros[k][1]]
            if nums:
                ms = sorted(set(k for k in ms if all(abs(k - x) > 1 for x in nums)) | set(nums))
        cabezas, grupos = _agrupar(ms)
        miembros = {k for g in grupos.values() for k in g[1:]}
        trozos = []
        for trozo in _partir(pal, frase, cabezas, A, grupos):
            # v5.48 (pedido: «jamás 4 líneas»): UNA palabra grande por bloque; el corte va justo después de la primera (sus palabras pequeñas
            # siguientes van con la segunda: «pero en la / Fiesta» + «se desató el / Show»). (_partir no se toca: lo usan los temas 1 y 3.)
            heads = [k for k in trozo if k in cabezas]
            for h in heads[1:]:
                fin0 = grupos.get(heads[heads.index(h) - 1], [heads[heads.index(h) - 1]])[-1]
                trozos.append([k for k in trozo if k <= fin0])
                trozo = [k for k in trozo if k > fin0]
            trozos.append(trozo)
        for trozo in trozos:
            plan.append({'frase': n_frase, 'palabras': trozo, 'mains': [k for k in trozo if k in cabezas], 'grupos': grupos, 'miembros': miembros,
                         'orig': sorted(o for k in trozo for o in pal[k]['orig'])})
    if A.get('complejos', True) and not forzados:
        plan = _complejos(plan, pal, A)
    plan = _reglas_lineas(plan, pal, A)
    plan = _juntar_cortos(plan, pal, A)
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
        segs = _lineas_pequenas(pal, segs, A)

        def texto_de(ks):
            if ks and ks[0] in numeros and list(ks) == numeros[ks[0]][1]:
                return numeros[ks[0]][0]       # (el texto que lee el Luxe Count: «$430,000», «50%»)
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
            elif ks and ks[0] in numeros and list(ks) == numeros[ks[0]][1]:
                e = VARIANTE_COUNT                                 # una cantidad: cuenta hasta la cifra
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
        alturas, anchos, m_a, arriba = [], {}, 0, {}
        for j, (tipo, ks) in enumerate(segs):
            if tipo == 'M':
                anchos[j] = _ancho_objetivo_main(texto_de(ks))
                if m_a < len(est):
                    natural = G.ancho_main(texto_de(ks), est[m_a], pack, ancho_tl)
                    vecinas = [segs[v] for v in (j - 1, j + 1) if 0 <= v < len(segs) and segs[v][0] == 'S']
                    if vecinas:
                        # v5.48 (pedido): la grande ocupa el ancho de su línea pequeña más ancha (la de encima o la de debajo): el Luxe Slide queda justo
                        # sobre ella, casi al ras, y la de debajo nunca se sale de ella. Nunca más pequeña que su tamaño natural, ni más del 92 % del cuadro.
                        w_linea = max(_ancho_linea(pal, v[1], A, forzar_peso, ancho_tl) for v in vecinas)
                        minimo = natural / float(ancho_tl) if natural else 0.0
                        tope = (A['zoom_max_cifra'] if est[m_a] == VARIANTE_COUNT else 2.4) * natural / float(ancho_tl) if natural else 0.92
                        anchos[j] = min(0.92, max(A['grande_linea'] * w_linea, A['grande_min'] * minimo), tope)     # (una cifra corta no crece tanto)
                    elif natural:                                               # sola (sin línea pequeña): no se infla (la referencia: zoom 0,9-1,3)
                        anchos[j] = min(anchos[j], A['zoom_max'] * natural / float(ancho_tl))
                aire = 2 * AIRE_EDITORIAL if (m_a < len(est) and est[m_a] in ESTILOS_EDITORIAL) else 0.0
                # v5.48: el alto REAL de su tinta en su tipografía (antes una estimación por letras: «EMPEZAMOS» reservaba 266 px y mide 114)
                # y lo que sube y baja respecto a la y del clip (Fusion centra la caja de la letra, no la tinta: «Maquillaje» cuelga por abajo)
                ext = G.extension_tinta(texto_de(ks), est[m_a], anchos[j], pack, ancho_tl) if m_a < len(est) else None
                if ext:
                    arriba[j] = ext[0]
                    alturas.append(ext[0] + ext[1])
                else:
                    alturas.append(_alto_main(texto_de(ks), anchos[j], ancho_tl, A, est[m_a] if m_a < len(est) else None) + aire)
                m_a += 1
            else:
                alturas.append(A['alto_linea'])
        total = sum(alturas) + A['hueco'] * (len(alturas) - 1)
        yc = ANCLAS.get(ancla, ANCLAS['medio'])
        if ancla == 'alterna':
            yc = (ANCLAS['medio'], ANCLAS['medio'], ANCLAS['alto'])[n % 3]
        top = max(0.10, min(0.90 - total, yc - total / 2.0))
        lineas, y, m_i = [], top, 0
        for j, ((tipo, ks), h) in enumerate(zip(segs, alturas)):
            centro = round(y + arriba.get(j, h / 2.0), 4)
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
                w_n = natural * G.AFINADO['tinta_pequena']
                cx, w_l = 0.5, (0.92 if w_n > 0.92 else None)
                if m_i > 0 and est[m_i - 1] not in ESTILOS_LINEA3_CENTRADA:
                    # v5.48 (pedido): la línea de DEBAJO de la grande va del centro hacia la derecha y NUNCA se sale del borde derecho de la grande
                    w_main = anchos[max(i for i in anchos if i < j)] - 0.03          # (margen: que la tinta quede DENTRO del borde, no justo en él)
                    if w_n >= w_main:
                        w_l = w_main
                    else:
                        cx = round(min(0.5 + w_n / 2.0, 0.5 + w_main / 2.0 - w_n / 2.0), 4)
                lineas.append(('S', [(t, p, round(tt, 3)) for t, p, tt in tr], cx, centro, w_l))
        b['estilo_bloque'] = est[0] if est else None
        b['grandes'] = sorted(o for tipo, ks in segs if tipo == 'M' for k_g in ks for o in pal[k_g]['orig'])       # las palabras que quedaron GRANDES (índices entregados)
        # la caja de la pila (fracción del alto, desde arriba): el emoji del bloque se coloca encima o debajo de ella
        bloques.append({'t0': b['t0'], 't1': b['t1'], 'estilo': est[0] if est else None, 'lineas': lineas, 'caja': (round(top, 4), round(top + total, 4))})
    _respiro(bloques, fin_video, A)
    return bloques, plan


def _respiro(bloques, fin_video=None, A=AFINADO):
    """v5.48: la última palabra de cada bloque se ve al menos A['respiro'] s. Si el bloque siguiente llega antes, espera (como mucho A['espera_max'] s)
    y sus palabras que entrarían antes de aparecer él entran con él. Antes la última palabra podía verse 0,1 s («muy rápido, no fluye»)."""
    def entradas(b):
        return [x[1] if l[0] == 'M' else x[2] for l in b['lineas'] for x in l[1]]
    for i, b in enumerate(bloques):
        quiere = max(b['t1'], max(entradas(b) or [b['t0']]) + A['respiro'])
        if i + 1 < len(bloques):
            sig = bloques[i + 1]
            fin = min(quiere, sig['t0'] - A['gap_minimo'] + A['espera_max'])
            if fin > sig['t0'] - A['gap_minimo']:
                nuevo = round(fin + A['gap_minimo'], 3)
                sig['t0'], sig['t1'] = nuevo, round(max(sig['t1'], nuevo + 0.6), 3)
                for n, l in enumerate(sig['lineas']):
                    if l[0] == 'M':
                        items = [(x[0], max(x[1], nuevo), x[2]) for x in l[1]]
                    else:
                        items = [(x[0], x[1], max(x[2], nuevo)) for x in l[1]]
                    sig['lineas'][n] = (l[0], items) + tuple(l[2:])
            b['t1'] = round(max(b['t1'], fin), 3)
        else:
            b['t1'] = round(max(b['t1'], min(float(fin_video), quiere) if fin_video else quiere), 3)


def cues_de(palabras, idioma='es', pack='Referencia', ancho_tl=1080, **kw):
    """Atajo: planifica y deja los bloques listos para el JSON de place_guion_track. El pack «Tema4» (Tema 4) arma sus bloques con su propio planificador (tema4_planificador.py:
    recuadro, tres tamaños de letra, palabras que aparecen una a una) pero usa el mismo colocador de Resolve."""
    if pack in ('Tema4', 'Tema5', 'Tema6'):                   # los Temas 5 y 6: los bloques del Tema 4 con el diseño de sus captions (v5.5.8, tema4_planificador.DISENOS)
        import tema4_planificador
        return tema4_planificador.cues_de(palabras, idioma, pack, ancho_tl, **kw)
    kw.pop('video', None)                                      # (solo lo usa el Tema 5: el color de la frase clave)
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
