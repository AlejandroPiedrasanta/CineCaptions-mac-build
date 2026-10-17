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
    'lab': dict(k='k label', cap=0.0125, max=2),
    'ser': dict(k='k serif blanco', cap=0.046, max=3),
    'tp_a': dict(k='k tape amarillo', cap=0.026, max=3, rot=-3.0, solape=0.12),
    'tp_l': dict(k='k tape lima', cap=0.024, max=3, rot=2.5, solape=0.10),
    'tp_r': dict(k='k tape rojo', cap=0.034, max=2, rot=-2.0, solape=0.12),
    'tp_b': dict(k='k tape blanco', cap=0.020, max=3, rot=1.5, solape=0.14),
    'tp_m': dict(k='k tape magenta', cap=0.027, max=2, rot=-2.5, solape=0.12),
    'ts_a': dict(k='k tapes amarillo', cap=0.040, max=2, rot=-2.0, solape=0.08),
    'ts_m': dict(k='k tapes magenta', cap=0.034, max=2, rot=2.0, solape=0.10),
    'sc_a': dict(k='k script amarillo', cap=0.050, max=2, rot=-5.0, solape=0.08),
    'sc_c': dict(k='k script cian', cap=0.046, max=2, rot=-6.0, solape=0.15),
    'sc_r': dict(k='k script rosa', cap=0.048, max=2, rot=-4.0, solape=0.15),
}
# prioridad al QUITAR huecos cuando hay menos palabras que huecos (lo primero que se va es lo menos importante)
PRIORIDAD_QUITAR = ('lab', 'sup', 'sup2', 'ser', 'tp_b', 'tp_l', 'tp_m', 'ts_m', 'tp_a', 'ts_a', 'tp_r', 'sc_c', 'sc_r', 'sc_a')

RECETAS = [
    dict(nombre='lima', heroe='k hero lima', cap=0.082, deco=('k line lima', 'heroe'),
         antes={1: ['sup2'], 2: ['sup2'], 3: ['sup2'], 4: ['sup', 'sup2']},
         despues={1: ['tp_a'], 2: ['tp_a'], 3: ['sup', 'tp_a'], 4: ['sup', 'tp_a']}),
    dict(nombre='blanco-rojo', heroe='k hero blanco', cap=0.105, deco=None, anillo_ultima=('k ring naranja', 'ser'),
         antes={1: ['sup'], 2: ['sup'], 3: ['sup'], 4: ['lab', 'sup']},
         despues={1: ['tp_r'], 2: ['tp_a', 'ser'], 3: ['tp_a', 'ser'], 4: ['tp_a', 'tp_r', 'ser']}),
    dict(nombre='magenta', heroe='k hero magenta', cap=0.088, deco=None,
         antes={1: ['sup'], 2: ['sup'], 3: ['sup2'], 4: ['lab', 'sup2']},
         despues={1: ['sc_a'], 2: ['tp_b', 'sc_a'], 3: ['tp_b', 'sc_a'], 4: ['tp_b', 'sup', 'sc_a']}),
    dict(nombre='amarillo', heroe='k hero amarillo', cap=0.092, deco=('k line magenta', 'heroe'), anillo_primera=('k ring rosa', 'ser'),
         antes={1: ['ser'], 2: ['ser'], 3: ['ser', 'ts_a'], 4: ['ser', 'sup']},
         despues={1: ['sup'], 2: ['sup'], 3: ['sup'], 4: ['sup', 'sup']}),
    dict(nombre='serif', heroe='k tapes amarillo', cap=0.062, deco=None, max_heroe=11,
         antes={1: ['lab'], 2: ['lab', 'ser'], 3: ['lab', 'ser'], 4: ['lab', 'ser']},
         despues={1: ['sc_a'], 2: ['sup', 'sc_a'], 3: ['sup', 'sc_a'], 4: ['sup', 'sc_a']}),
    dict(nombre='blanco-cian', heroe='k hero blanco', cap=0.098, deco=None, anillo_ultima=('k ring rosa', 'sc_c'),
         antes={1: ['sup'], 2: ['sup'], 3: ['sup', 'tp_m'], 4: ['sup', 'tp_m']},
         despues={1: ['sc_c'], 2: ['sup', 'sc_c'], 3: ['sup', 'sc_c'], 4: ['tp_l', 'sup', 'sc_c']}),
]


def _patron(tabla, n):
    """El patrón de huecos para n palabras: el de la tabla, o el del mayor n conocido con líneas pequeñas delante."""
    if n <= 0:
        return []
    if n in tabla:
        return list(tabla[n])
    return list(tabla[max(tabla)])                       # más palabras que huecos: los huecos admiten varias palabras (no se añaden líneas)


ACENTOS = ('ser', 'tp_a', 'tp_l', 'tp_r', 'tp_b', 'tp_m', 'ts_a', 'ts_m', 'sc_a', 'sc_c', 'sc_r')


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


def _heroe(pal, bloque, forzados=None):
    """Índice de la palabra héroe del bloque."""
    if forzados:
        f = [k for k in bloque if k in forzados]
        if f:
            return f[0]
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
    if receta.get('max_heroe') and len(texto_h) > receta['max_heroe']:
        receta = RECETAS[1]                                # un héroe larguísimo no cabe en la cinta serif: receta de héroe condensado
    pos = bloque.index(h)
    antes, despues = bloque[:pos], bloque[pos + 1:]
    if despues and any(ch.isdigit() for ch in pal[despues[0]]['texto']) and len(pal[despues[0]]['texto']) <= 3:
        texto_h = f"{texto_h} {pal[despues[0]]['texto']}"        # «número 1»: la cifra suelta se queda con su palabra, no flota debajo
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
    lh = dict(heroe=True, k=clave_h, texto=texto_h, t=max(0.0, pal[h]['t'] - AFINADO['adelanto']), cap=cap_h, rot=0.0, solape=0.0, nombre='heroe', idx=[h])
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
    return dict(lineas=lineas, receta=receta['nombre'], heroe=h, palabras=bloque, ancla=ancla)


def planificar(palabras, idioma='es', ancho_tl=1080, alto_tl=1920, ancla='bajo', mains=None, recetas=None, fin_video=None):
    """palabras [{'word','start','end'}] -> {'cues': [...], 'plan': [...]} . `mains`: palabras (texto) o índices forzados como héroe. `recetas`: {índice de bloque: n de receta}."""
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
    bloques = []
    ultimo_fin = (pal[-1]['fin'] if pal else 0.0)
    for i, b in enumerate(bloques_idx):
        k_receta = (recetas or {}).get(i, i)
        info = armar_bloque(pal, b, k_receta, forzados or None, y_ancla)
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
    cues = KC.construir_cues(bloques, ancho_tl, alto_tl)
    plan = [dict(i=b['indice'], receta=b['receta'], heroe=pal[b['heroe']]['texto'], texto=' '.join(pal[k]['texto'] for k in b['palabras']), t0=round(b['t0'], 2), t1=round(b['t1'], 2))
            for b in bloques]
    for c, b in zip(cues, bloques):
        c['lines'] = [{'role': 'main' if l['nombre'] == 'heroe' else 'context', 'text': l['texto'], 'start': l['t']} for l in b['lineas'] if l.get('texto')]
    return {'cues': cues, 'plan': plan}


def resumen(res):
    """El plan en una tabla legible."""
    filas = ['  # receta        héroe            t0 → t1     texto']
    for p in res['plan']:
        filas.append(f"{p['i']:3d} {p['receta']:<13s} {p['heroe']:<16s} {p['t0']:5.2f} → {p['t1']:5.2f}  {p['texto']}")
    return '\n'.join(filas)
