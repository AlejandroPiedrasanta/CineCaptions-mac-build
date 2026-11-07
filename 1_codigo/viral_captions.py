# CineCaptions · By Cinema Productions
# 1_codigo/viral_captions.py — estilo «VIRAL»: la geometría de la pila (tamaños con la tipografía real, posiciones, tiempos) y el .json para Resolve.
"""
viral_captions.py  (v5.5)
-------------------------
El estilo VIRAL (carpeta «ESTILO VIRAL» del usuario): cada frase es una pila de LÍNEAS; cada línea son palabras sueltas que entran cuando se dicen, unas finas
(«v fina»), otras en negrita cursiva («v negrita»), y la palabra con más peso puede llevar un EFECTO: «v shatter» (azul cielo que se rompe como un vidrio), «v select» (se escribe y se
selecciona con un cursor) o «v drag» (una mano la arrastra y la rellena). Se van todas a la vez al acabar la frase.

Este módulo NO elige qué palabra lleva qué (eso es viral_planificador.py) ni habla con Resolve: recibe LÍNEAS de ITEMS
    {'k': clip del pack («v fina»), 'texto', 't': cuándo entra (s), 'cap': altura de las mayúsculas (fracción del alto)}
las mide con su tipografía real (Pillow), pone las palabras de cada línea en fila (alineadas por la base), apila las líneas centradas en un ancla vertical y devuelve los
runs que lee place_kinetic_track (CineCaptions.py / .lua; el mismo colocador que Kinetic):
    {'language': 'es', 'cues': [{'start', 'end', 'runs': [{'k', 'texto', 't', 'fin', 'x', 'y', 'size'}]}]}
    x, y = centro del elemento (fracción del cuadro; y desde ARRIBA) · size = «Size» del Text+.
"""
import kinetic_captions as KC

K_PX = 691.0                         # px del em por unidad de «Size» de Text+ a 1080 px de ancho: Inter rinde ~8 % más que el 640 de las fuentes de Kinetic (medido con 'HHHH' a Size 0,2: mayúsculas 102 px)
INTER_18 = ('Inter 18pt', 'Medium')
INTER_28_EXTRA = ('Inter 28pt', 'ExtraBold')
INTER_28_NEGRA = ('Inter 28pt', 'Black')
# lo que sabe la geometría de cada clip del pack (debe coincidir con generador_packs/viral_elementos.py): (tipografía, espaciado de letras)
CLIPS = {'v fina': (INTER_18, 1.0), 'v negrita': (INTER_28_EXTRA, 0.99), 'v shatter': (INTER_28_NEGRA, 0.97), 'v select': (INTER_28_NEGRA, 0.97), 'v drag': (INTER_28_NEGRA, 0.97),
         'v corte': (INTER_28_NEGRA, 0.97), 'v shine': (INTER_28_NEGRA, 0.97), 'v resalta': (INTER_28_EXTRA, 0.97)}   # v5.75: «Crea tu estilo» (fuera de la rotación del Tema 3)
BARLOW = ('Barlow Semi Condensed', 'Bold')
CLIPS.update({'v linea': (BARLOW, 0.975), 'v linea activa': (BARLOW, 0.975), 'v linea activa azul': (BARLOW, 0.975)})      # v5.75: el Tema 3 nuevo (linea_planificador; su geometría va allí)
EFECTOS = ('v shatter', 'v select', 'v drag')
# v5.5: cada efecto viene en 4 COLORES (el primero es el de siempre: shatter azul cielo, select con caja roja, drag blanco); el planificador los va alternando para que el color no se repita.
# El clip de la variante se llama «<efecto> <color>» («v shatter rosa»); la geometría (tipografía, tamaño, espacio) es la del efecto base.
COLORES = {'v shatter': ('', 'rosa', 'lima', 'oro'), 'v select': ('', 'azul', 'verde', 'naranja'), 'v drag': ('', 'amarillo', 'cian', 'rosa')}


def base_de(clave):
    """'v shatter rosa' -> 'v shatter' (el efecto del que es variante); lo que no es una variante sale igual."""
    for base in COLORES:
        if clave == base or str(clave).startswith(base + ' '):
            return base
    return clave


def nombre_variante(base, k):
    """El clip del efecto `base` para su aparición número k (0, 1, 2…): rota por los 4 colores. Para lo que no tiene variantes devuelve `base`."""
    paleta = COLORES.get(base)
    if not paleta:
        return base
    c = paleta[int(k) % len(paleta)]
    return base + (' ' + c if c else '')


def todos_los_clips():
    """Los nombres de todos los clips de efecto (cada efecto con sus variantes de color)."""
    return [nombre_variante(b, k) for b in COLORES for k in range(len(COLORES[b]))]
CAP = {'Inter 18pt': 0.737, 'Inter 28pt': 0.728, 'Barlow Semi Condensed': 0.70}            # altura de las mayúsculas / em (medida con Pillow)
# el centro del cuadro de Text+ queda a esta fracción del em por ENCIMA/DEBAJO del centro de las mayúsculas (medido contra el render de Resolve; Inter: 0)
DY_EM = {'Inter 18pt': 0.0, 'Inter 28pt': 0.0, 'Barlow Semi Condensed': 0.0}
INCLINADA = {'v negrita': 0.21}                              # cuánto ensancha la cursiva sintética (× altura de mayúsculas)
TINTA = 0.985                                                # lo que se ve de una palabra respecto a su avance tipográfico

# lo que sobresale cada efecto de su línea (× altura de mayúsculas): la caja de «select» y la mano de «drag» no deben pisar a las líneas vecinas
SOBRESALE = {'v select': (0.50, 0.55), 'v drag': (0.45, 0.10), 'v shatter': (0.08, 0.08), 'v corte': (0.10, 0.14), 'v shine': (0.10, 0.10),
             'v resalta': (0.20, 0.40)}
# v5.75: lo que sale a cada lado de la tinta (× altura de mayúsculas): los trozos del «corte» se separan hasta ~0,41 em (izquierda) y ~0,35 em
# (derecha); la caja del «resalta» sale 0,05 em y la bolita de su asa otros 0,08
LADOS = {'v corte': 0.60, 'v resalta': 0.20}
AFINADO = {'ancho_max': 0.88, 'hueco_linea': 0.55, 'hueco_min': 0.010, 'espacio': 0.42, 'min_size': 0.03}
# v5.55: el cursor del «select» (viral_elementos.comp_select, ~0,54 × 0,37 em) cuelga de la esquina de abajo a la derecha de su caja hasta ~1,2 mayúsculas bajo la
# base: (lo que baja más allá de SOBRESALE, lo que sale la caja a cada lado de la tinta, el ancho de la flecha), × su altura de mayúsculas. Abajo solo se le deja
# sitio si la línea de debajo llega hasta él (si es más estrecha, el cursor cuelga a su lado); a los lados, la fila del «select» cabe con su caja y su cursor
CURSOR_SELECT = (0.70, 0.40, 0.50)
MARGEN_CUADRO = 0.02            # v5.55: lo que la pila deja libre en los bordes del cuadro contando lo que sobresale (caja y cursor del «select», la mano…) (× alto o × ancho)


def _par(clave):
    return CLIPS.get(base_de(clave), CLIPS['v fina'])


def _fuente(par, px):
    return KC._fuente(par, px)


def ancho_px(clave, texto, size, ancho_tl=1080):
    """Ancho (px) de la tinta de `texto` en el clip `clave` con ese «Size» de Text+."""
    (par, esp) = _par(clave)
    px = size * K_PX * ancho_tl / 1080.0
    f = _fuente(par, px)
    avance = f.getlength(texto) if f is not None else len(texto) * px * 0.55
    return avance * esp * TINTA + INCLINADA.get(clave, 0.0) * CAP[par[0]] * px * 0.5


def size_para_cap(clave, cap_px, ancho_tl=1080):
    (par, _esp) = _par(clave)
    return cap_px / CAP[par[0]] / (K_PX * ancho_tl / 1080.0)


def cap_de_size(clave, size, ancho_tl=1080):
    (par, _esp) = _par(clave)
    return size * K_PX * ancho_tl / 1080.0 * CAP[par[0]]


def lado_de_referencia(ancho_tl, alto_tl):
    """Los px a los que se refieren las alturas de mayúsculas (fracciones): el lado corto × 16/9 = el alto de un vertical (1920 a 1080 de ancho) o el ancho de un horizontal 1080p. Así el texto
    mide lo mismo en píxeles en vertical y en horizontal (47 px de mayúsculas de la palabra fina a 1080 px de lado corto) y escala con la resolución."""
    return min(ancho_tl, alto_tl) * 16.0 / 9.0


def _medir_linea(items, ancho_tl, alto_tl):
    """Completa los items de una línea: size, ancho (px), cap (px) y el ancho total; si no cabe, la línea entera se reduce."""
    ref = lado_de_referencia(ancho_tl, alto_tl)
    for it in items:
        it['cap_px'] = float(it['cap']) * ref
        it['size'] = size_para_cap(it['k'], it['cap_px'], ancho_tl)
        it['w'] = ancho_px(it['k'], it['texto'], it['size'], ancho_tl)
    gap = AFINADO['espacio'] * min(it['cap_px'] for it in items)
    total = sum(it['w'] for it in items) + gap * (len(items) - 1)
    maximo = AFINADO['ancho_max'] * ancho_tl
    f = 1.0
    if total > maximo:
        f = maximo / total
    sel = next((it for it in items if base_de(it['k']) == 'v select'), None)
    if sel is not None:         # v5.55: la fila del «select» cabe en el cuadro con la caja a los dos lados y el cursor a la derecha (crecen con la letra)
        extra = (2 * CURSOR_SELECT[1] + CURSOR_SELECT[2]) * sel['cap_px']
        f = min(f, ancho_tl * (1 - 2 * MARGEN_CUADRO) / (total + extra))
    lados = sum(2 * LADOS[base_de(it['k'])] * it['cap_px'] for it in items if base_de(it['k']) in LADOS)
    if lados:                   # v5.75: la fila cabe con los trozos del «corte» ya separados o la caja y el asa del «resalta»
        f = min(f, ancho_tl * (1 - 2 * MARGEN_CUADRO) / (total + lados))
    if f < 1.0:
        for it in items:
            it['size'] *= f
            it['cap_px'] *= f
            it['w'] = ancho_px(it['k'], it['texto'], it['size'], ancho_tl)
        gap *= f
        total = sum(it['w'] for it in items) + gap * (len(items) - 1)
    return gap, total


def _inicio_x(items, gap, total, ancho_tl):
    """Dónde empieza (px) la fila: centrada; v5.55: si lleva un «select» cuyo cursor se saldría por la derecha, corrida a la izquierda lo justo."""
    x0 = 0.5 * ancho_tl - total / 2.0
    x = x0
    for it in items:
        if base_de(it['k']) == 'v select':
            derecha = x + it['w'] + (CURSOR_SELECT[1] + CURSOR_SELECT[2]) * it['cap_px']
            return x0 - max(0.0, derecha - ancho_tl * (1 - MARGEN_CUADRO))
        x += it['w'] + gap
    return x0


def _cursor(items, gap, total, ancho_tl):
    """(dónde empieza en x el cursor del «select» de la fila, la mayúscula del «select») en px, o None si la fila no lleva «select»."""
    x = _inicio_x(items, gap, total, ancho_tl)
    for it in items:
        if base_de(it['k']) == 'v select':
            return x + it['w'] + CURSOR_SELECT[1] * it['cap_px'], it['cap_px']
        x += it['w'] + gap
    return None


def apilar(lineas, ancla_y, ancho_tl=1080, alto_tl=1920):
    """lineas = [[items]] -> los mismos items con 'x', 'y' (centro, fracción del cuadro) y la caja [arriba, abajo] de la pila (fracción del alto, desde arriba)."""
    medidas = []
    for items in lineas:
        gap, total = _medir_linea(items, ancho_tl, alto_tl)
        medidas.append((gap, total, max(it['cap_px'] for it in items)))
    y = 0.0
    tops = []
    previo = None
    abajo_previo = 0.0
    cursor_previo = None
    for items, (gap, total, cap) in zip(lineas, medidas):
        arriba_l = max((SOBRESALE.get(base_de(it['k']), (0, 0))[0] * it['cap_px'] for it in items), default=0.0)
        abajo_l = max((SOBRESALE.get(base_de(it['k']), (0, 0))[1] * it['cap_px'] for it in items), default=0.0)
        if previo is not None:
            bajo_cursor = cursor_previo and 0.5 * ancho_tl + total / 2.0 > cursor_previo[0]          # esta línea llega debajo del cursor de la de arriba
            y += (max(AFINADO['hueco_min'] * lado_de_referencia(ancho_tl, alto_tl), AFINADO['hueco_linea'] * min(previo, cap)) + arriba_l + abajo_previo
                  + (CURSOR_SELECT[0] * cursor_previo[1] if bajo_cursor else 0.0))
        tops.append(y)
        y += cap
        previo = cap
        abajo_previo = abajo_l
        cursor_previo = _cursor(items, gap, total, ancho_tl)
    alto_total = y
    arriba = ancla_y * alto_tl - alto_total / 2.0
    if lineas:                  # v5.55: contando lo que sobresale arriba de la primera línea y abajo de la última (con el cursor), la pila no se sale del cuadro
        sobra_arriba = max((SOBRESALE.get(base_de(it['k']), (0, 0))[0] * it['cap_px'] for it in lineas[0]), default=0.0)
        sobra_abajo = abajo_previo + (CURSOR_SELECT[0] * cursor_previo[1] if cursor_previo else 0.0)
        margen = MARGEN_CUADRO * alto_tl
        arriba -= max(0.0, arriba + alto_total + sobra_abajo - (alto_tl - margen))
        arriba += max(0.0, margen - (arriba - sobra_arriba))
    for items, (gap, total, cap), top in zip(lineas, medidas, tops):
        base = arriba + top + cap                       # la línea de base de la fila
        x = _inicio_x(items, gap, total, ancho_tl)
        for it in items:
            (par, _e) = _par(it['k'])
            centro_y = base - it['cap_px'] / 2.0 + DY_EM[par[0]] * it['cap_px'] / CAP[par[0]]
            it['x'] = round((x + it['w'] / 2.0) / ancho_tl, 4)
            it['y'] = round(centro_y / alto_tl, 4)
            x += it['w'] + gap
    caja = (round(arriba / alto_tl, 4), round((arriba + alto_total) / alto_tl, 4))
    return lineas, caja


def construir_cues(bloques, ancho_tl=1080, alto_tl=1920):
    """bloques: [{'t0', 't1', 'ancla', 'tipo', 'lineas': [[item…]]}] -> cues con 'runs' listos para el .json."""
    cues = []
    for b in bloques:
        lineas, caja = apilar([[dict(it) for it in fila] for fila in b['lineas']], b.get('ancla', 0.64), ancho_tl, alto_tl)
        runs = []
        for fila in lineas:
            for it in fila:
                runs.append({'k': it['k'], 't': round(float(it.get('t', b['t0'])), 3), 'fin': round(float(it.get('fin', b['t1'])), 3), 'x': it['x'], 'y': it['y'],
                             'texto': it['texto'], 'size': round(it['size'], 4)})
        runs.sort(key=lambda r: (r['t'], r['x']))
        cues.append({'start': round(b['t0'], 3), 'end': round(b['t1'], 3), 'plantilla': b.get('tipo'), 'caja': list(caja), 'runs': runs})
    return cues


escribir = KC.escribir
