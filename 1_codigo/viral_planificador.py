# CineCaptions · By Cinema Productions
# 1_codigo/viral_planificador.py — del texto con tiempos (ASR) a los bloques del estilo «VIRAL»: frases, palabra con efecto, líneas finas y negritas, y momentos.
"""
viral_planificador.py  (v5.5)
-----------------------------
Convierte las palabras con tiempos que entrega la voz en los bloques que arma viral_captions.construir_cues, imitando la carpeta «ESTILO VIRAL»:

  1. FRASES y BLOQUES: las mismas reglas que «guion» y «Kinetic» (guion_planificador.frases / _partir: signo fuerte, pausa, ≤ 7 palabras por bloque).
  2. PALABRA CLAVE: en cada bloque la de más peso (kinetic_planificador._heroe: puntajes de guion_planificador, o la que el usuario pintó como «Principal» en Creativo).
  3. TIPO DE BLOQUE, determinista (mismo audio → mismo resultado):
       · «pila»  (ESTILO VIRAL 3) palabras finas + la clave en negrita cursiva, una o dos por frase; las líneas se cortan después de cada negrita.
       · «efecto» la clave va sola en grande con un EFECTO que rota —«v select» (se escribe y se selecciona), «v shatter» (azul cielo que se rompe como un vidrio), «v drag» (una mano la
         arrastra)—, con las palabras finas de antes encima y las de después debajo. Toca un efecto cada `cada` bloques (por defecto 2: pila, efecto, pila, efecto…),
         siempre en las palabras que el usuario pintó como Principal (y, si pintó alguna, SOLO en ellas), y NUNCA (salvo las pintadas) si no hay tiempo para que el efecto se vea entero (entonces el bloque es una pila).
  4. TIEMPOS: cada palabra entra cuando se dice; la pila entera se va un instante después de la última, sin pisar al bloque siguiente (como Kinetic: se acorta lo que sobra
     y, si no cabe, el siguiente se retrasa ≤ 0,4 s). Un bloque con efecto se queda lo que el efecto necesita para verse entero.

Se puede forzar a mano: `mains=` (palabras o índices que llevan efecto) y `efectos=` ({índice de bloque: clip}).
"""
import re

import guion_planificador as G
import kinetic_planificador as KP
import viral_captions as VC

ANCLAS = {'medio': 0.50, 'alto': 0.30, 'bajo': 0.64}
ANCLAS_HORIZONTAL = {'medio': 0.50, 'alto': 0.30, 'bajo': 0.72}      # un horizontal tiene el tercio inferior más abajo
AFINADO = {'adelanto': 0.03, 'hold': 0.30, 'min_bloque': 0.9, 'gap_minimo': 0.10, 'min_ultimo': 0.55, 'visible_min': 0.45, 'desfase_max': 0.4, 'max_palabras': 7,
           'cada': 2, 'max_fina': 3, 'max_efecto_letras': 14, 'holgura_efecto': 0.5}
# cuánto tiene que verse cada efecto (s desde que entra la palabra) para llegar a su estado final
DURACION = {'v shatter': 1.1, 'v select': 1.35, 'v drag': 1.4}
# lo MÍNIMO que tiene que verse cada efecto (s desde que entra la palabra) para llegar a su estado final con el tiempo comprimido al máximo (×2)
MINIMO = {'v shatter': 0.60, 'v select': 0.70, 'v drag': 0.70}
ROTACION = ('v select', 'v shatter', 'v drag')           # en este orden salen; si el que toca no cabe en el tiempo del bloque, se prueba el siguiente (antes se caía siempre a shatter)
CAP = {'v fina': 0.0245, 'v negrita': 0.040, 'v shatter': 0.072, 'v select': 0.072, 'v drag': 0.072}
# la palabra con efecto es más grande cuanto más corta
ESCALA_LARGO = ((4, 1.18), (6, 1.0), (9, 0.9), (99, 0.8))


def _mayus(t):
    return t[:1].upper() + t[1:] if t else t


def _escala(n):
    for tope, f in ESCALA_LARGO:
        if n <= tope:
            return f
    return 1.0


def _lineas_finas(pal, idx, maximo):
    """Las palabras finas `idx` en filas de a lo sumo `maximo` palabras, REPARTIDAS por igual (7 → 3·2·2, nunca 3·3·1: una palabra suelta queda huérfana)."""
    if not idx:
        return []
    n_filas = -(-len(idx) // maximo)
    base, extra = divmod(len(idx), n_filas)
    filas, i = [], 0
    for r in range(n_filas):
        n = base + (1 if r < extra else 0)
        filas.append(idx[i:i + n])
        i += n
    return filas


def _item(pal, k, clave, adelanto=True, cifra=None):
    texto = _mayus(pal[k]['texto'])
    if cifra is not None:                                      # «número» «1»: la cifra suelta se queda con su palabra, no flota debajo
        texto = f"{texto} {pal[cifra]['texto']}"
    return dict(k=clave, texto=texto, t=max(0.0, pal[k]['t'] - (AFINADO['adelanto'] if adelanto else 0.0)), cap=CAP[clave], idx=k)


def _cifra_pegada(pal, despues):
    """Índice de la cifra suelta (≤ 3 caracteres con algún dígito) que va justo después de la palabra clave, o None."""
    if despues and any(ch.isdigit() for ch in pal[despues[0]]['texto']) and len(pal[despues[0]]['texto']) <= 3:
        return despues[0]
    return None


def armar_bloque(pal, bloque, tipo, efecto=None, forzados=None, ancla=0.64, idx_bloque=0, max_fina=None):
    """El bloque (índices de palabras) -> {'lineas': [[items]], 'tipo', 'heroe', ...}. Las líneas salen de arriba abajo; `tipo` = 'pila' | 'efecto'."""
    max_fina = max_fina or AFINADO['max_fina']
    h = KP._heroe(pal, bloque, forzados)
    pos = bloque.index(h)
    antes, despues = bloque[:pos], bloque[pos + 1:]
    cifra = _cifra_pegada(pal, despues)
    if cifra is not None:
        despues = despues[1:]
    lineas = []
    if tipo == 'efecto':
        for fila in _lineas_finas(pal, antes, max_fina):
            lineas.append([_item(pal, k, 'v fina') for k in fila])
        it = _item(pal, h, efecto or ROTACION[0], cifra=cifra)
        it['cap'] = CAP[it['k']] * _escala(len(it['texto']))
        it['heroe'] = True
        lineas.append([it])
        for fila in _lineas_finas(pal, despues, max_fina):
            lineas.append([_item(pal, k, 'v fina') for k in fila])
        return dict(lineas=lineas, tipo=efecto, heroe=h, palabras=bloque, ancla=ancla)
    # pila: las negritas son la clave y, en frases largas, otra palabra con peso lejos de ella; las líneas se cortan DESPUÉS de cada negrita
    negritas = {h}
    if len(bloque) >= 5:
        pts = G.puntajes(pal, bloque)
        otras = sorted((k for k in pts if abs(bloque.index(k) - pos) >= 3 and pts[k] >= G.AFINADO['puntaje_2']), key=lambda k: (-pts[k], k))
        if otras:
            negritas.add(otras[0])
    fila, finas = [], []
    for k in bloque:
        if k == cifra:                                           # ya va pegada a la palabra clave
            continue
        if k in negritas:
            if len(finas) >= 2:                                  # «About The / Bakery»: varias finas antes van en su propia fila
                for f in _lineas_finas(pal, finas, max_fina):
                    lineas.append([_item(pal, j, 'v fina') for j in f])
                finas = []
            fila = [_item(pal, j, 'v fina') for j in finas] + [_item(pal, k, 'v negrita', cifra=cifra if k == h else None)]
            fila[-1]['heroe'] = (k == h)
            lineas.append(fila)
            finas = []
        else:
            finas.append(k)
    for f in _lineas_finas(pal, finas, max_fina):      # lo que se dice después de la última negrita
        lineas.append([_item(pal, j, 'v fina') for j in f])
    return dict(lineas=lineas, tipo='pila', heroe=h, palabras=bloque, ancla=ancla)


def _retrasar(bloque, d):
    """Retrasa el INICIO del bloque `d` segundos: las palabras que ya habrían entrado salen todas a la vez al arrancar y las demás conservan su momento real (el retraso no se arrastra a
    las últimas palabras: con habla muy rápida, desplazar todas se encadenaba con el bloque siguiente y las dejaba fuera de tiempo)."""
    nuevo = bloque['t0'] + d
    for fila in bloque['lineas']:
        for it in fila:
            it['t'] = max(it['t'], nuevo)
    bloque['t0'] = nuevo


def _bloques_con_tiempos(pal, bloques_idx, tipos, forzados, y_ancla, fin_video, ultimo_fin, max_fina=None):
    """Arma los bloques con su tipo y les pone los tiempos: cuándo entra cada palabra y cuándo se va la pila (sin pisar a la siguiente)."""
    bloques = []
    for i, b in enumerate(bloques_idx):
        tipo, ef = tipos[i]
        info = armar_bloque(pal, b, tipo, ef, forzados or None, y_ancla, i, max_fina)
        items = [it for fila in info['lineas'] for it in fila]
        t0 = max(0.0, min(it['t'] for it in items))
        fin_hablado = max(pal[k]['fin'] for k in b)
        info.update(t0=t0, fin_hablado=fin_hablado, indice=i)
        bloques.append(info)
    # 3) cierres: la pila se va un instante después de la última palabra y NUNCA se solapa con la del bloque siguiente (como Kinetic)
    for i, b in enumerate(bloques):
        ultimo_el = max(it['t'] for fila in b['lineas'] for it in fila)
        minimo = AFINADO['min_bloque']
        if b['tipo'] in DURACION:
            heroe_t = next(it['t'] for fila in b['lineas'] for it in fila if it.get('heroe'))
            minimo = max(minimo, heroe_t - b['t0'] + DURACION[b['tipo']] + 0.1)
        t1 = max(b['fin_hablado'] + AFINADO['hold'], b['t0'] + minimo, ultimo_el + AFINADO['min_ultimo'])
        if i + 1 < len(bloques):
            sig = bloques[i + 1]
            limite = sig['t0'] - AFINADO['gap_minimo']
            if b['tipo'] in DURACION and t1 > limite:                  # un efecto no se corta: antes se retrasa un poco el bloque siguiente (hasta DESFASE_MAX)
                _retrasar(sig, min(t1 - limite, AFINADO['desfase_max']))
                limite = sig['t0'] - AFINADO['gap_minimo']
            if t1 > limite:
                t1 = max(limite, ultimo_el + AFINADO['visible_min'])
                if t1 > limite:                                   # ni acortando cabe: se retrasa el bloque siguiente
                    _retrasar(sig, min(t1 + AFINADO['gap_minimo'] - sig['t0'], AFINADO['desfase_max']))
                    t1 = min(t1, sig['t0'] - AFINADO['gap_minimo'])
        else:
            fin = fin_video if fin_video else ultimo_fin + 1.0
            t1 = min(t1, fin - AFINADO['gap_minimo']) if fin - AFINADO['gap_minimo'] > ultimo_el + AFINADO['visible_min'] else max(ultimo_el + AFINADO['visible_min'], t1)
        b['t1'] = t1
    return bloques


def unir_fragmentos(palabras, idioma='es'):
    """El ASR a veces parte una cifra o una palabra compuesta en dos («$15» «,000», «full» «-time»; y el GO ya quitó la coma: «$15» «000»): se pegan, con el tiempo de las dos.
    Cada palabra devuelta lleva en '_o' los índices de la lista ORIGINAL de los que sale (las marcas del editor Creativo se cuentan sobre esa lista)."""
    sal = []
    for j, p in enumerate(palabras):
        w = str(p.get('word', ''))
        previa = str(sal[-1].get('word', '')) if sal else ''
        if sal and re.fullmatch(r'\d{3}', w.strip()) and re.fullmatch(r'\W?\d{1,3}', previa.strip()) and float(p.get('start', 0.0)) - float(sal[-1].get('end', 0.0)) < 0.3:
            ant = dict(sal[-1])
            ant['word'] = previa.strip() + (',' if str(idioma).lower().startswith('en') else '.') + w.strip()
            ant['end'] = p.get('end', ant.get('end'))
            ant['_o'] = list(ant['_o']) + [j]
            sal[-1] = ant
        elif sal and re.match(r'^[,.\-–]\w', w.strip()) and not previa.rstrip().endswith(('.', '!', '?', '…')):
            ant = dict(sal[-1])
            ant['word'] = previa.rstrip() + w.strip()
            ant['end'] = p.get('end', ant.get('end'))
            ant['_o'] = list(ant['_o']) + [j]
            sal[-1] = ant
        else:
            q = dict(p)
            q['_o'] = [j]
            sal.append(q)
    return sal


def planificar(palabras, idioma='es', ancho_tl=1080, alto_tl=1920, ancla='bajo', mains=None, efectos=None, fin_video=None, cada=None):
    """palabras [{'word','start','end'}] -> {'cues': [...], 'plan': [...]} . `mains`: palabras (texto) o índices forzados (llevan efecto). `efectos`: {índice de bloque: clip}."""
    unidas = unir_fragmentos(palabras, idioma)
    pal = G._preparar(unidas)
    if not pal:
        return {'cues': [], 'plan': []}
    for w in pal:                                                # los índices de la lista ORIGINAL de cada palabra (las marcas de Creativo cuentan sobre ella)
        w['orig_real'] = sorted({o for jm in w.get('orig', ()) for o in unidas[jm]['_o']})
    horizontal = ancho_tl > alto_tl
    tabla = ANCLAS_HORIZONTAL if horizontal else ANCLAS
    y_ancla = tabla.get(ancla, tabla['bajo']) if not isinstance(ancla, (int, float)) else float(ancla)
    max_fina = 5 if horizontal else AFINADO['max_fina']                   # una fila de un horizontal admite más palabras que una de un vertical
    cada = cada or AFINADO['cada']
    forzados = set()
    for m in (mains or []):
        if isinstance(m, int):
            forzados.update(k for k, w in enumerate(pal) if m in w['orig_real'])
        else:
            forzados.update(k for k, w in enumerate(pal) if w['plano'] == G._plano(str(m)))
    bloques_idx = []
    for k_frase, frase in enumerate(G.frases(pal)):
        mp = G.elegir_mains(pal, frase, primera=(k_frase == 0), forzados=forzados or None)
        bloques_idx += G._partir(pal, frase, mp)
    ultimo_fin = pal[-1]['fin']
    # 1) qué bloques llevan efecto (y cuál): los forzados siempre; el resto cada `cada` bloques, si hay tiempo
    tipos, rot = [], 0
    for i, b in enumerate(bloques_idx):
        h = KP._heroe(pal, b, forzados or None)
        letras = len(pal[h]['texto'])
        forzado = h in forzados
        sig_t = pal[bloques_idx[i + 1][0]]['t'] if i + 1 < len(bloques_idx) else None
        quiere = (efectos or {}).get(i)
        pedido = quiere if isinstance(quiere, str) else None                   # un efecto pedido a mano (efectos={índice: clip}) no rota
        if quiere is None:
            quiere = forzado or (not forzados and i % cada == cada - 1)       # con palabras marcadas en Creativo, el efecto va SOLO en ellas; sin marcas (GO) se reparte solo
        if quiere:
            disponible = (sig_t - pal[h]['t']) if sig_t is not None else (((fin_video or ultimo_fin + 1.5) - pal[h]['t']))
            disponible += 0.75 * AFINADO['desfase_max']                        # el bloque siguiente puede retrasarse un poco
            candidatos = [pedido, 'v shatter'] if pedido else [ROTACION[(rot + k) % len(ROTACION)] for k in range(len(ROTACION))]
            quiere = next((c for c in candidatos if disponible >= MINIMO[c]), None)       # el primero de la rotación que cabe (así no sale siempre el mismo)
            if quiere is None and forzado:
                quiere = 'v shatter'                                           # en las palabras que el usuario marcó el efecto sale siempre (el más corto)
            if letras > AFINADO['max_efecto_letras'] or letras < 2:
                quiere = None
        if quiere:
            rot = ROTACION.index(quiere) + 1 if not pedido else rot + 1        # la siguiente vez toca el que sigue al que salió
            tipos.append(('efecto', quiere))
        else:
            tipos.append(('pila', None))
    # 2) los bloques con sus tiempos; si un efecto se queda sin el tiempo mínimo (el bloque anterior lo retrasó, el siguiente llega ya), baja a «shatter» (el más corto)
    # o a pila y se recalcula: así ningún efecto se ve a medias
    for _ in range(4):
        bloques = _bloques_con_tiempos(pal, bloques_idx, tipos, forzados, y_ancla, fin_video, ultimo_fin, max_fina)
        cambio = False
        for i, b in enumerate(bloques):
            if b['tipo'] not in DURACION:
                continue
            heroe_t = next(it['t'] for fila in b['lineas'] for it in fila if it.get('heroe'))
            if b['t1'] - heroe_t < MINIMO[b['tipo']] - 0.02:
                if b['tipo'] != 'v shatter' and b['t1'] - heroe_t >= MINIMO['v shatter'] - 0.02:
                    tipos[i] = ('efecto', 'v shatter')
                    cambio = True
                elif b['heroe'] not in forzados:
                    tipos[i] = ('pila', None)
                    cambio = True
        if not cambio:
            break
    # los COLORES de los efectos: la primera vez que sale cada efecto es el de siempre (shatter azul cielo, caja roja, drag blanco) y las siguientes rotan por rosa/lima/oro, azul/verde/naranja y
    # amarillo/cian/rosa (viral_captions.COLORES): el color no se repite seguido
    veces = {}
    for b in sorted(bloques, key=lambda x: x['t0']):
        if b['tipo'] in VC.COLORES:
            k = veces.get(b['tipo'], 0)
            veces[b['tipo']] = k + 1
            nuevo = VC.nombre_variante(b['tipo'], k)
            for fila in b['lineas']:
                for it in fila:
                    if it['k'] == b['tipo']:
                        it['k'] = nuevo
            b['tipo'] = nuevo
    cues = VC.construir_cues(bloques, ancho_tl, alto_tl)
    plan = [dict(i=b['indice'], tipo=b['tipo'], heroe=pal[b['heroe']]['texto'], texto=' '.join(pal[k]['texto'] for k in b['palabras']), t0=round(b['t0'], 2), t1=round(b['t1'], 2))
            for b in bloques]
    for c, b in zip(cues, bloques):
        c['lines'] = [{'role': 'main' if any(it.get('heroe') for it in fila) else 'context', 'text': ' '.join(it['texto'] for it in fila),
                       'start': next((it['t'] for it in fila if it.get('heroe')), min(it['t'] for it in fila))}        # la fila de la clave arranca con la clave (el emoji y el golpe de sonido entran con ella)
                      for fila in b['lineas']]
    return {'cues': cues, 'plan': plan}


def resumen(res):
    """El plan en una tabla legible."""
    filas = ['  # tipo        clave            t0 → t1     texto']
    for p in res['plan']:
        filas.append(f"{p['i']:3d} {str(p['tipo']):<11s} {p['heroe']:<16s} {p['t0']:5.2f} → {p['t1']:5.2f}  {p['texto']}")
    return '\n'.join(filas)
