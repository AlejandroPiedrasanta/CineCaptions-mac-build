# CineCaptions · By Cinema Productions
# 1_codigo/kinetic_planificador.py — del texto con tiempos (ASR) a los bloques del estilo «Kinetic»: frases, palabra héroe, receta (plantilla), elementos y momentos.
"""
kinetic_planificador.py  (v5.4)
-------------------------------
Convierte las palabras con tiempos que entrega la voz en los bloques que arma kinetic_captions.construir_cues, imitando los títulos de gancho de la
referencia («Vertical Kinetic Hook Titles»):

  1. FRASES y BLOQUES: las mismas reglas que el estilo «guion» (guion_planificador.frases / _partir: signo fuerte, pausa, ≤ 7 palabras por bloque).
  2. HÉROE: en cada bloque la palabra con más peso (guion_planificador.puntajes) es la palabra gigante condensada; lo que se dice ANTES va encima y
     lo que se dice DESPUÉS va debajo.
  3. RECETA: cada bloque estrena una receta de las seis (rotan, como las plantillas de la referencia): «TOO SLOW / PEOPLE SCROLL / START FASTER» (héroe lima +
     cinta amarilla + subrayado), «NO / Clear / MESSAGE» (héroe blanco + cinta roja), «DON'T MAKE THEM / THINK / Feel.» (héroe magenta + pincel),
     «ADD Captions / TIME» (serif + héroe amarillo + subrayado), «FOCUS / ON HOOK / NOT / DESIGN» (etiqueta + serif + cinta serif) y «PEOPLE / JUDGE / KNOW you.»
     (héroe blanco + cinta magenta + pincel cian + anillo). Cada receta dice QUÉ ELEMENTO (línea pequeña, serif, cinta, pincel…) lleva cada hueco de
     antes y de después según cuántas palabras haya.
  4. TIEMPOS: cada elemento entra cuando se dice su primera palabra; la pila entera se va un instante después de la última, sin pisar al bloque siguiente.

Todo es determinista (mismo audio → mismos bloques) y se puede forzar a mano: `mains=` (palabras o índices) y `recetas=` (por índice de bloque).
"""
import guion_planificador as G
import kinetic_captions as KC

ANCLAS = {'medio': 0.50, 'alto': 0.30, 'bajo': 0.64}
AFINADO = {'adelanto': 0.03, 'hold': 0.28, 'min_bloque': 0.95, 'gap_minimo': 0.10, 'min_ultimo': 0.5, 'visible_min': 0.45, 'desfase_max': 0.4, 'max_palabras': 7}

# --- los elementos que puede llevar un hueco: clip del pack, altura de las mayúsculas (fracción del alto), palabras máximas, giro, si solapa al héroe
S = {
    'sup': dict(k='k sup', cap=0.0225, max=4),
    'sup2': dict(k='k sup', cap=0.030, max=4),
    'lab': dict(k='k label', cap=0.0130, max=4),                    # v5.5.13 (neón): las versalitas espaciadas del kit («¿VIVES O ESTÁS»)
    'ser': dict(k='k serif blanco', cap=0.032, max=3),              # (kit: la serif es más pequeña que el héroe: «de paso por», «esto es»)
    'tp_a': dict(k='k tape amarillo', cap=0.026, max=3, rot=-3.0, solape=0.12),
    'tp_l': dict(k='k tape lima', cap=0.044, max=2, rot=-3.5, solape=0.10),
    'tp_r': dict(k='k tape rojo', cap=0.048, max=2, rot=-4.0, solape=0.14),
    'tp_b': dict(k='k tape blanco', cap=0.040, max=2, rot=5.0, solape=0.30),
    'tp_m': dict(k='k tape magenta', cap=0.044, max=2, rot=-3.0, solape=0.08),
    'ts_a': dict(k='k tapes amarillo', cap=0.040, max=2, rot=-2.0, solape=0.08),
    'ts_m': dict(k='k tapes magenta', cap=0.034, max=2, rot=2.0, solape=0.10),
    'sc_a': dict(k='k script amarillo', cap=0.050, max=2, rot=-5.0, solape=0.08),
    'sc_c': dict(k='k script cian', cap=0.046, max=2, rot=-6.0, solape=0.15),
    'sc_r': dict(k='k script rosa', cap=0.048, max=2, rot=-4.0, solape=0.15),
    'sc_l': dict(k='k script yt lima', cap=0.048, max=3, rot=0.0, solape=0.10),        # v5.5.13 (neón): la palabra a mano (Yellowtail); v5.47 recta (el usuario: «está torcido»; era −7°)
    'sc_m': dict(k='k script yt magenta', cap=0.048, max=3, rot=0.0, solape=0.10),       # v5.47 recta (era −6°)
}
# prioridad al QUITAR huecos cuando hay menos palabras que huecos (lo primero que se va es lo menos importante)
PRIORIDAD_QUITAR = ('lab', 'sup', 'sup2', 'ser', 'tp_b', 'tp_l', 'tp_m', 'ts_m', 'tp_a', 'ts_a', 'tp_r', 'sc_c', 'sc_r', 'sc_a', 'sc_m', 'sc_l')

# v5.5.13 — TEMA NEÓN (kit Escritorio/TEMA 1, ejemplo_xela/escenas.js): las seis recetas copian los bloques `hook()` del ejemplo. Los nombres no cambian
# (son los ids «t1:lima»… de «Crea tu estilo» y de los packs guardados). Trazos a mano: 'circulo' (rodea al héroe), 'lazo' (rodea al héroe y a la pegatina
# que lo sigue; sin pegatina, círculo) y 'subraya' (debajo de una línea: 'heroe' o el nombre de un hueco).
RECETAS = [
    # «¿VIVES O ESTÁS / de paso por / XELA?» + círculo lima
    dict(nombre='lima', heroe='k hero lima', cap=0.088, circulo='k ring trazo lima',
         antes={1: ['ser'], 2: ['ser'], 3: ['lab', 'ser'], 4: ['lab', 'ser']},
         despues={1: ['sup'], 2: ['sup'], 3: ['sup', 'sup'], 4: ['sup', 'sup']}),
    # «SI ES ASÍ / DEJA / TODO» (pegatina roja inclinada)
    dict(nombre='blanco-rojo', heroe='k hero blanco', cap=0.100,
         antes={1: ['lab'], 2: ['lab'], 3: ['lab'], 4: ['lab', 'ser']},
         despues={1: ['tp_r'], 2: ['tp_r'], 3: ['tp_r', 'ser'], 4: ['tp_r', 'ser']}),
    # «porque esto te / INTERESA» + subrayado lima
    dict(nombre='magenta', heroe='k hero magenta', cap=0.090, subraya=('k line trazo lima', 'heroe'),
         antes={1: ['ser'], 2: ['ser'], 3: ['ser'], 4: ['lab', 'ser']},
         despues={1: ['sup'], 2: ['sup'], 3: ['sup', 'sup'], 4: ['sup', 'sup']}),
    # «trae a / QUETZALTENANGO» (a mano lima + héroe blanco) y, si sigue algo, pegatina magenta («3 JÓVENES / INFLUENCERS»)
    dict(nombre='amarillo', heroe='k hero blanco', cap=0.088,
         antes={1: ['sc_l'], 2: ['sc_l'], 3: ['lab', 'sc_l'], 4: ['lab', 'sc_l']},
         despues={1: ['tp_m'], 2: ['tp_m'], 3: ['tp_m', 'sup'], 4: ['tp_m', 'sup']}),
    # «EL FESTIVAL DEL / PODER / DE &» (héroe lima + pegatina blanca) + lazo magenta
    dict(nombre='serif', heroe='k hero lima', cap=0.086, lazo='k ring lazo magenta',
         antes={1: ['lab'], 2: ['lab'], 3: ['lab'], 4: ['lab', 'ser']},
         despues={1: ['tp_b'], 2: ['tp_b'], 3: ['tp_b', 'sup'], 4: ['tp_b', 'sup']}),
    # «HABRÁN / CONCIERTOS / en vivo» + subrayado magenta bajo la palabra a mano
    dict(nombre='blanco-cian', heroe='k hero blanco', cap=0.095, subraya=('k line trazo magenta', 'sc_l'),
         antes={1: ['lab'], 2: ['lab'], 3: ['lab'], 4: ['lab', 'sup']},
         despues={1: ['sc_l'], 2: ['sc_l'], 3: ['sc_l', 'sup'], 4: ['sc_l', 'sup']}),
]


def _color_contrario(k_trazo, k_texto):
    """v5.47 (el usuario: «los rings de otro color, no el mismo que el texto»): un aro, lazo o subrayado nunca del color de lo que marca:
    lima sobre lima pasa a magenta y magenta sobre magenta a lima (la receta «lima» ponía un aro lima alrededor de la palabra lima)."""
    for a, b in (('lima', 'magenta'), ('magenta', 'lima')):
        if str(k_trazo).endswith(' ' + a) and str(k_texto).endswith(' ' + a):
            return str(k_trazo)[:-len(a)] + b
    return k_trazo


def _patron(tabla, n):
    """El patrón de huecos para n palabras: el de la tabla, o el del mayor n conocido con líneas pequeñas delante."""
    if n <= 0:
        return []
    if n in tabla:
        return list(tabla[n])
    return list(tabla[max(tabla)])                       # más palabras que huecos: los huecos admiten varias palabras (no se añaden líneas)


ACENTOS = ('ser', 'tp_a', 'tp_l', 'tp_r', 'tp_b', 'tp_m', 'ts_a', 'ts_m', 'sc_a', 'sc_c', 'sc_r', 'sc_l', 'sc_m')


def _repartir(indices, huecos, pal=None):
    """[(hueco, [índices])] — reparte las palabras (en orden) entre los huecos (en orden): una por hueco y las que sobren a los huecos con capacidad."""
    huecos = list(huecos)
    while len(huecos) > len(indices):                     # menos palabras que huecos: se quita el menos importante
        for nombre in PRIORIDAD_QUITAR:
            if nombre in huecos:
                huecos.remove(nombre)
                break
        else:
            huecos.pop(0)
    if not huecos:
        return []
    cuentas = [1] * len(huecos)
    sobran = len(indices) - len(huecos)
    while sobran > 0:
        avance = False
        for i, h in enumerate(huecos):
            if sobran > 0 and cuentas[i] < S[h]['max']:
                cuentas[i] += 1
                sobran -= 1
                avance = True
        if not avance:
            cuentas[-1] += sobran                         # nada admite más: lo que sobra va al último hueco
            break
    salida, c = [], 0
    for h, n in zip(huecos, cuentas):
        grupo = indices[c:c + n]
        if pal is not None and h in ACENTOS and (all(pal[i]['plano'] in G.STOP for i in grupo) or len(' '.join(pal[i]['texto'] for i in grupo)) <= 2
                                                 or any(ch.isdigit() for ch in ' '.join(pal[i]['texto'] for i in grupo))):
            h = 'sup'                                         # un acento (cinta, serif, pincel) pide una palabra con peso: no «de», «1», «hay»…
        salida.append((h, grupo))
        c += n
    return salida


# v5.5.17: nunca la palabra grande (en «networking con OTROS + pegatina jóvenes», «otros» no dice nada)
DETERMINANTES = {'otros', 'otras', 'otro', 'otra', 'todos', 'todas', 'muchos', 'muchas', 'algunos', 'algunas', 'varios', 'varias', 'cada', 'mismo',
                 'misma', 'mismos', 'mismas', 'nuestro', 'nuestra', 'nuestros', 'nuestras', 'vuestro', 'vuestra', 'other', 'others', 'some', 'many',
                 'every', 'each', 'our', 'their', 'outros', 'outras', 'muitos', 'muitas'}


def _es_cifra(pal, k):
    """v5.5.17: «3», «10» o «tres»/«diez» (2–99 dicho con letra; «un/una» no: son artículos)."""
    import edicion_pro_planificador as PL
    t = pal[k]['texto'].strip('.,;:!?¡¿"' + "'")
    if t.isdigit() and len(t) <= 4:
        return True
    v = PL.NUM_PALABRAS.get(PL.plegar(t))
    return isinstance(v, int) and 2 <= v <= 99 and PL.plegar(t) not in PL._NO_CIFRA


def _cifra_con_nombre(pal, bloque):
    """v5.5.17 (kit: «3 JÓVENES» grande + pegatina «INFLUENCERS»): el índice de una cifra seguida de su sustantivo («3 jóvenes», «10 consejos»),
    o None. No «10 de octubre» (fecha) ni «a las 10» (hora): el sustantivo va JUSTO detrás y no es una palabra vacía."""
    for j, k in enumerate(bloque[:-1]):
        n = bloque[j + 1]
        if (_es_cifra(pal, k) and pal[n]['plano'] not in G.STOP and len(pal[n]['plano']) >= 3 and not _es_cifra(pal, n)
                and not any(s in pal[n]['texto'] for s in '%$€')):
            return k
    return None


def _porcentaje(pal, bloque):
    """v5.5.17: «100 %» en DOS palabras (el reconocimiento de voz separa el signo): el índice de la cifra, o None."""
    for j, k in enumerate(bloque[:-1]):
        if pal[k]['texto'].strip('.,').isdigit() and pal[bloque[j + 1]]['texto'].strip('.,') in ('%', 'por ciento', 'percent'):
            return k
    return None


def _heroe(pal, bloque, forzados=None):
    """Índice de la palabra héroe del bloque."""
    if forzados:
        f = [k for k in bloque if k in forzados]
        if f:
            return f[0]
    # v5.5.13 (neón): una cantidad con %, $ o € es la palabra grande del bloque (kit: «LA ENTRADA ES / 100% / GRATUITA»)
    cant = [k for k in bloque if any(ch.isdigit() for ch in pal[k]['texto']) and any(s in pal[k]['texto'] for s in '%$€')]
    if cant:
        return cant[0]
    pc = _porcentaje(pal, bloque)
    if pc is not None:
        return pc
    pts = G.puntajes(pal, bloque)
    if pts:
        mejor = max(pts, key=lambda k: (pts[k], len(pal[k]['plano']), -k))
        if len(pal[mejor]['plano']) <= 4:                      # una palabra muy corta no hace de héroe si hay otra de peso y más larga
            largas = [k for k in pts if len(pal[k]['plano']) >= 6 and pts[k] >= pts[mejor] - 4]
            if largas:
                mejor = max(largas, key=lambda k: (pts[k], len(pal[k]['plano'])))
        return mejor
    return max(bloque, key=lambda k: (len(pal[k]['plano']), -k))


def _cap_heroe(base, texto, receta):
    n = len(texto)
    f = 1.0
    if n <= 3:
        f = 1.28
    elif n <= 5:
        f = 1.08
    elif n >= 10:
        f = 0.82
    elif n >= 8:
        f = 0.92
    return base * f


def armar_bloque(pal, bloque, k_receta, forzados=None, ancla=0.64):
    """El bloque (índices de palabras) -> {'lineas', 'receta', 't0', ...}. Las líneas salen de arriba abajo."""
    h = _heroe(pal, bloque, forzados)
    receta = RECETAS[k_receta % len(RECETAS)]
    texto_h = pal[h]['texto']
    idx_h = [h]
    num = _cifra_con_nombre(pal, bloque) if not (forzados and any(k in forzados for k in bloque)) else None
    if num is not None and _porcentaje(pal, bloque) is None:
        # v5.5.17 (kit: «3 JÓVENES» grande —la cifra en el acento— y lo que sigue en la pegatina magenta: «INFLUENCERS»)
        h, idx_h = num, [num, bloque[bloque.index(num) + 1]]
        texto_h = f"{pal[num]['texto']} {pal[idx_h[1]]['texto']}"
        receta = RECETAS[3]
    elif _porcentaje(pal, bloque) == h:
        idx_h = [h, bloque[bloque.index(h) + 1]]                 # (v5.5.17: «100 %» → «100%», una sola palabra grande)
        texto_h = pal[h]['texto'].strip('.,') + '%'
    if receta.get('max_heroe') and len(texto_h) > receta['max_heroe']:
        receta = RECETAS[1]                                # un héroe larguísimo no cabe en la cinta serif: receta de héroe condensado
    pos = bloque.index(h)
    antes, despues = bloque[:pos], bloque[pos + len(idx_h):]
    if despues and ((any(s in pal[h]['texto'] for s in '%$€') and any(ch.isdigit() for ch in pal[h]['texto'])) or texto_h.endswith('%')):
        # (kit: tras la cantidad, lo que es va en una pegatina roja: «100%» + «GRATUITA»)
        receta = dict(receta, despues={n: ['tp_r'] + list(v[1:]) for n, v in receta['despues'].items()})
    # v5.5.13 (neón): en las recetas de pegatina, si la palabra fuerte es la última («si es así deja TODO») va en la pegatina y la de antes hace de
    # palabra grande, como el kit («DEJA» + pegatina «TODO», «3 JÓVENES» + «INFLUENCERS»)
    pegatina = (receta['despues'].get(1) or [''])[0]
    if pegatina.startswith('tp_') and not despues and antes and not (forzados and h in forzados) and len(idx_h) == 1:
        previa = antes[-1]
        if (pal[previa]['plano'] not in G.STOP and pal[previa]['plano'] not in DETERMINANTES and len(pal[previa]['plano']) >= 3
                and not any(ch.isdigit() for ch in pal[previa]['texto'])):
            h, antes, despues = previa, antes[:-1], [h]
            texto_h = pal[h]['texto']
    if despues and any(ch.isdigit() for ch in pal[despues[0]]['texto']) and len(pal[despues[0]]['texto']) <= 3 and len(idx_h) == 1:
        texto_h = f"{texto_h} {pal[despues[0]]['texto']}"        # «número 1»: la cifra suelta se queda con su palabra, no flota debajo
        idx_h = idx_h + [despues[0]]
        despues = despues[1:]
    lineas = []

    def linea(nombre, idx, base=None, **extra):
        e = dict(S[nombre])
        d = dict(k=e['k'], texto=' '.join(pal[i]['texto'] for i in idx), t=max(0.0, min(pal[i]['t'] for i in idx) - AFINADO['adelanto']),
                 cap=e['cap'], rot=e.get('rot', 0.0), solape=e.get('solape', 0.0), nombre=nombre, idx=list(idx))
        d.update(extra)
        return d

    for nombre, idx in _repartir(antes, _patron(receta['antes'], len(antes)), pal):
        lineas.append(linea(nombre, idx))
    clave_h = receta['heroe']
    cap_h = _cap_heroe(receta['cap'], texto_h, receta)
    lh = dict(heroe=True, k=clave_h, texto=texto_h, t=max(0.0, pal[h]['t'] - AFINADO['adelanto']), cap=cap_h, rot=0.0, solape=0.0, nombre='heroe', idx=list(idx_h))
    if clave_h.startswith('k tapes'):
        lh['rot'] = -2.0
    lineas.append(lh)
    for nombre, idx in _repartir(despues, _patron(receta['despues'], len(despues)), pal):
        lineas.append(linea(nombre, idx))
    # los trazos: se enganchan a una línea por su posición entre las líneas de texto
    textos = [l for l in lineas]
    indice_h = next(i for i, l in enumerate(textos) if l['nombre'] == 'heroe')
    deco = receta.get('deco')
    if deco and len(despues) <= 1 and not clave_h.startswith('k tapes'):
        lineas.append(dict(k=deco[0], texto='', t=lh['t'] + 0.12, cap=0.0, sobre=indice_h, rel_w=0.9, sep=0.016 if len(despues) == 0 else 0.010, nombre='deco'))
    for atributo, extremo in (('anillo_ultima', -1), ('anillo_primera', 0)):
        a = receta.get(atributo)
        if not a:
            continue
        candidatas = [i for i, l in enumerate(textos) if l['nombre'] == a[1] and len(str(l.get('texto') or '')) <= 14]       # un anillo rodea una palabra corta
        if candidatas:
            i = candidatas[extremo]
            textos[i]['anillo'] = True                      # la pila le deja sitio al anillo (si no, pisaba a la línea de al lado)
            lineas.append(dict(k=a[0], texto='', t=textos[i]['t'] + 0.1, cap=0.0, sobre=i, nombre='anillo'))
    # v5.5.13 (neón): los trazos a mano del kit; entran cuando ya está escrito lo que rodean o subrayan (kit: +0,18 s el círculo, +0,3 s el lazo)
    lazo = receta.get('lazo') and _color_contrario(receta['lazo'], clave_h)
    if lazo:
        sig = next((i for i in range(indice_h + 1, len(textos)) if textos[i]['nombre'].startswith('tp_')), None)
        if sig is not None and sig == indice_h + 1:
            lineas.append(dict(k=lazo, texto='', t=textos[sig]['t'] + 0.30, cap=0.0, sobre=[indice_h, sig], nombre='trazo'))
        else:
            lineas.append(dict(k=lazo.replace('lazo', 'trazo'), texto='', t=lh['t'] + 0.18, cap=0.0, sobre=indice_h, nombre='trazo'))
    if receta.get('circulo'):
        lineas.append(dict(k=_color_contrario(receta['circulo'], clave_h), texto='', t=lh['t'] + 0.18, cap=0.0, sobre=indice_h, nombre='trazo'))
    sub = receta.get('subraya')
    if sub:
        i = indice_h if sub[1] == 'heroe' else next((j for j, l in enumerate(textos) if l['nombre'] == sub[1]), None)
        if i is not None:
            lineas.append(dict(k=_color_contrario(sub[0], textos[i]['k']), texto='', t=textos[i]['t'] + 0.20, cap=0.0, sobre=i, rel_w=0.9, sep=0.014, nombre='deco'))
    return dict(lineas=lineas, receta=receta['nombre'], heroe=h, palabras=bloque, ancla=ancla)


def _como_el_kit(b, pal, idioma):
    """v5.44 (Tema 1 con Text+ editables, «que quede igual que antes»): las líneas del bloque con las reglas de composición del kit (kit_neon.bloque_hook):
    números de 2 a 99 en cifra («3 JÓVENES»), la pregunta en la grande («XELA?») y abierta con «¿», nunca dos versalitas apiladas («A UNA» +
    «BECA DE» → «A UNA BECA DE»; más de 4 palabras → serif) y ninguna versalita DEBAJO de la grande (pasa a serif). Los trazos siguen a su línea."""
    import kit_neon as KN
    serif = next(v for v in S.values() if v['k'] == 'k serif blanco')
    nuevas, mapa, visto_big = [], {}, False

    def tipo(l):
        if l.get('nombre') == 'heroe':
            return 'big' if str(l['k']).startswith('k hero') else 'otro'
        return 'esp' if l['k'] in ('k label', 'k sup') else 'serif' if str(l['k']).startswith('k serif') else 'otro'
    for i, l in enumerate(b['lineas']):
        if not l.get('texto'):
            continue
        l = dict(l, texto=KN._cifras(l['texto']), idx=list(l.get('idx') or []))
        k = tipo(l)
        if k == 'esp' and l['k'] != 'k label':                  # (v5.45: el kit tiene UNA versalita, Inter espaciada; «k sup» es la condensada)
            l.update(k='k label', cap=next(v for v in S.values() if v['k'] == 'k label')['cap'])
        if l.get('nombre') == 'heroe':
            visto_big = visto_big or k == 'big'
            if l['idx'] and '?' in str(pal[l['idx'][-1]].get('signo') or '') and not l['texto'].endswith('?'):
                l['texto'] += '?'
        elif k == 'esp' and visto_big:
            l.update(k=serif['k'], cap=serif['cap'])
            k = 'serif'
        prev = nuevas[-1] if nuevas else None
        if prev is not None and tipo(prev) == 'esp' and k == 'esp' and len((prev['texto'] + ' ' + l['texto']).split()) > 4:
            l.update(k=serif['k'], cap=serif['cap'])
            k = 'serif'
        if prev is not None and tipo(prev) == k and k in ('esp', 'serif'):
            prev['texto'] = f"{prev['texto']} {l['texto']}"
            prev['idx'] = prev['idx'] + l['idx']
            mapa[i] = len(nuevas) - 1
            continue
        mapa[i] = len(nuevas)
        nuevas.append(l)
    if str(idioma or 'es')[:2] == 'es' and any(l['texto'].rstrip().endswith('?') for l in nuevas) and not any('¿' in l['texto'] for l in nuevas):
        nuevas[0]['texto'] = '¿' + nuevas[0]['texto'].lstrip()
    for l in b['lineas']:
        if l.get('texto'):
            continue
        sobre = l.get('sobre', 0)
        refs = sorted({mapa[i] for i in (sobre if isinstance(sobre, (list, tuple)) else [sobre]) if i in mapa})
        if refs:
            nuevas.append(dict(l, sobre=refs if isinstance(sobre, (list, tuple)) and len(refs) > 1 else refs[0]))
    b['lineas'] = nuevas
    return b


def planificar(palabras, idioma='es', ancho_tl=1080, alto_tl=1920, ancla='bajo', mains=None, recetas=None, fin_video=None, con_bloques=False, kit=False):
    """palabras [{'word','start','end'}] -> {'cues': [...], 'plan': [...]} . `mains`: palabras (texto) o índices forzados como héroe. `recetas`: {índice de bloque: n de receta}.
    v5.5.13: `con_bloques` añade 'bloques' (las líneas de cada bloque en el orden de la pila, con sus palabras) y 'pal' (las palabras preparadas):
    el Tema 1 neón (kit_neon.py) arma con ellos los bloques hook() del kit."""
    pal = G._preparar(palabras)
    if not pal:
        return {'cues': [], 'plan': []}
    y_ancla = ANCLAS.get(ancla, ANCLAS['bajo']) if not isinstance(ancla, (int, float)) else float(ancla)
    forzados = set()
    for m in (mains or []):
        if isinstance(m, int):
            # v5.5.10: índices de la lista ENTREGADA (las marcas de Creativo), no de `pal`, que quita vacías y junta tartamudeos: antes, tras una palabra
            # quitada, la Principal marcada caía en la palabra de al lado (marcar «licensed» hacía héroe a «FULL-TIME»), en la vista y en Resolve
            forzados.update(k for k, w in enumerate(pal) if m in w['orig'])
        else:
            forzados.update(k for k, w in enumerate(pal) if w['plano'] == G._plano(str(m)))
    bloques_idx = []
    for k_frase, frase in enumerate(G.frases(pal)):
        mp = G.elegir_mains(pal, frase, primera=(k_frase == 0), forzados=forzados or None)
        bloques_idx += G._partir(pal, frase, mp)
    # v5.5.17 (kit: «LA ENTRADA ES / 100% / GRATUITA»): un bloque que acaba en una cantidad se queda la palabra que la explica (la pegatina)
    for i in range(len(bloques_idx) - 1):
        b, sig = bloques_idx[i], bloques_idx[i + 1]
        fin_pc = len(b) >= 2 and _porcentaje(pal, b[-2:]) is not None
        fin_cant = any(ch.isdigit() for ch in pal[b[-1]]['texto']) and any(x in pal[b[-1]]['texto'] for x in '%$€')
        if (fin_pc or fin_cant) and len(sig) >= 3 and pal[sig[0]]['plano'] not in G.STOP and len(pal[sig[0]]['plano']) >= 3                 and pal[sig[0]]['t'] - pal[b[-1]]['fin'] < 0.6:
            bloques_idx[i], bloques_idx[i + 1] = b + [sig[0]], sig[1:]
    bloques = []
    ultimo_fin = (pal[-1]['fin'] if pal else 0.0)
    for i, b in enumerate(bloques_idx):
        k_receta = (recetas or {}).get(i, i)
        info = armar_bloque(pal, b, k_receta, forzados or None, y_ancla)
        if kit:                                           # v5.44: el Tema 1 con Text+: la composición del kit (los clips neón la hacían en kit_neon)
            info = _como_el_kit(info, pal, idioma)
        t0 = max(0.0, min(l['t'] for l in info['lineas']))
        fin_hablado = max(pal[k]['fin'] for k in b)
        info.update(t0=t0, fin_hablado=fin_hablado, indice=i)
        bloques.append(info)
    # cierres: la pila se va un instante después de la última palabra y NUNCA se solapa con la del bloque siguiente (dos pilas a la vez se pisan: las
    # dos van al mismo sitio). Si el siguiente llega antes de que este pueda irse con su última palabra visible lo justo (VISIBLE_MIN), primero se
    # acorta lo que se queda de más y, si ni así cabe, el siguiente bloque se retrasa un poco (como mucho DESFASE_MAX): mejor un título tarde que dos juntos.
    for i, b in enumerate(bloques):
        ultimo_el = max(l['t'] for l in b['lineas'])
        t1 = max(b['fin_hablado'] + AFINADO['hold'], b['t0'] + AFINADO['min_bloque'], ultimo_el + AFINADO['min_ultimo'])
        if i + 1 < len(bloques):
            sig = bloques[i + 1]
            limite = sig['t0'] - AFINADO['gap_minimo']
            if t1 > limite:
                t1 = max(limite, ultimo_el + AFINADO['visible_min'])
                if t1 > limite:                                   # ni acortando cabe: se retrasa el bloque siguiente
                    d = min(t1 + AFINADO['gap_minimo'] - sig['t0'], AFINADO['desfase_max'])
                    for l in sig['lineas']:
                        l['t'] += d
                    sig['t0'] += d
                    t1 = min(t1, sig['t0'] - AFINADO['gap_minimo'])
        else:
            fin = fin_video if fin_video else ultimo_fin + 1.0
            t1 = min(t1, fin - AFINADO['gap_minimo']) if fin - AFINADO['gap_minimo'] > ultimo_el + AFINADO['visible_min'] else max(ultimo_el + AFINADO['visible_min'], t1)
        b['t1'] = t1
    if kit:                                               # v5.45: la geometría del kit (tamaños y alturas de cada línea) para los Text+
        import kit_neon as KN
        for b in bloques:                                 # y sus tiempos: cada línea cuando se DICE su primera palabra (kit: max(t0, palabra) − 0,03),
            for l in b['lineas']:                         # no retrasada con el bloque (retrasar el bloque solo evita que dos pilas se pisen)
                if l.get('texto') and l.get('idx'):
                    l['t'] = max(b['t0'], min(pal[i]['t'] for i in l['idx']) - 0.03)
            textos = [l for l in b['lineas'] if l.get('texto')]
            quedan = []
            for l in b['lineas']:                         # los trazos como kit_neon.escena_captions: uno que empezaría en los últimos 0,5 s
                if l.get('texto') or not textos:          # entra antes (0,5 s antes de la salida, tras lo que rodea) y, sin 0,4 s para dibujarse, no va
                    quedan.append(l)
                    continue
                sobre = l.get('sobre', 0)
                refs = [textos[min(len(textos) - 1, int(i))] for i in (sobre if isinstance(sobre, (list, tuple)) else [sobre])]
                ti = max((float(r['t']) for r in refs), default=b['t0'])
                t = max(float(l['t']), b['t0'])
                if t > b['t1'] - 0.5:
                    t = max(b['t1'] - 0.5, ti + 0.05)
                if b['t1'] - t >= 0.4:
                    quedan.append(dict(l, t=round(t, 3)))
            b['lineas'] = quedan
        for i, b in enumerate(bloques):
            try:
                hook = KN.bloque_hook(b, pal, primero=(i == 0), ultimo=(i == len(bloques) - 1))
                textos = [l for l in b['lineas'] if l.get('texto')]
                if hook and len(hook['items']) == len(textos):
                    for l, m in zip(textos, KN.maqueta(hook)):
                        l['kit'] = m
            except Exception:
                pass
    cues = KC.construir_cues(bloques, ancho_tl, alto_tl)
    plan = [dict(i=b['indice'], receta=b['receta'], heroe=pal[b['heroe']]['texto'], texto=' '.join(pal[k]['texto'] for k in b['palabras']), t0=round(b['t0'], 2), t1=round(b['t1'], 2))
            for b in bloques]
    for c, b in zip(cues, bloques):
        c['lines'] = [{'role': 'main' if l['nombre'] == 'heroe' else 'context', 'text': l['texto'], 'start': l['t']} for l in b['lineas'] if l.get('texto')]
    if con_bloques:
        return {'cues': cues, 'plan': plan, 'bloques': bloques, 'pal': pal}
    return {'cues': cues, 'plan': plan}


def resumen(res):
    """El plan en una tabla legible."""
    filas = ['  # receta        héroe            t0 → t1     texto']
    for p in res['plan']:
        filas.append(f"{p['i']:3d} {p['receta']:<13s} {p['heroe']:<16s} {p['t0']:5.2f} → {p['t1']:5.2f}  {p['texto']}")
    return '\n'.join(filas)
