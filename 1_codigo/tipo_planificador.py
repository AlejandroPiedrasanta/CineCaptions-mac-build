# CineCaptions · By Cinema Productions
# 1_codigo/tipo_planificador.py — el Tema 5 (v5.76): bloques tipográficos con la palabra clave GRANDE y lo demás en serif cursiva que la muerde, palabra a palabra.
"""
tipo_planificador.py  (v5.76)
-----------------------------
El Tema 5 de la página Tema y de GO (referencia del usuario «cómo hacer ESTA TIPOGRAFÍA en capcut», propuesta B: todo blanco, la serif cursiva
«muerde» la palabra grande, palabra a palabra y con bisel de luz). Pedido: «aplícalo en Tema 5, elimina el estilo del Tema 5, coloca este y mételo
en texto principal en Crea tu estilo» (solo los captions: sus escenas PRO, pasos y deslizador siguen igual).

  1. BLOQUES: las frases de guion_planificador, partidas en trozos de ≤ MAX_PALABRAS palabras y ≤ MAX_SEGUNDOS de voz (repartidos parejos y sin
     dejar un artículo o una preposición colgando al final de un trozo).
  2. PALABRA CLAVE de cada bloque: la marcada como Principal en Creativo (`mains`) o la de más puntaje (guion_planificador.puntajes); va en
     MAYÚSCULAS grandes (Montserrat Black). Lo de antes, en serif cursiva encima (alineado a su izquierda); lo de después, debajo (a su derecha).
  3. MAQUETA: la de la propuesta que eligió el usuario (scratchpad tipo/bloque3d.html, a 720 de ancho): la grande llena ANCHO del cuadro con un tope
     de altura, la serif ocupa ~3/4 de la grande y se monta sobre ella. Medida con Pillow y llevada al Text+ con lo medido en Resolve 21.2.
  4. UN clip «v tipo» por bloque (viral_elementos.comp_tipo): todo va codificado en su texto (codificar) y cada palabra se escribe cuando se dice
     (Write On por letras, tabla de tiempos dentro del texto). Mismo contrato que viral_planificador.planificar ({'cues', 'plan'}) y mismo colocador.
"""
import math

import guion_planificador as G
import viral_captions as VC
import viral_planificador as VP
import zona_segura as ZS

CLIP = 'v tipo'
GRANDE = ('Montserrat', 'Black')             # = viral_elementos.TIPO_GRANDE
SERIF = ('DM Serif Text', 'Italic')          # = viral_elementos.TIPO_SERIF
# medido en Resolve 21.2 («HHHH» a Size 0,2 en un cuadro de 1080: mayúsculas de 99 px y 83 px): px del em por unidad de «Size» a 1080 de ancho,
# y dónde queda el centro del Text+ respecto del centro de las mayúsculas (em; negativo = más arriba)
K_PX = {GRANDE: 707.1, SERIF: 627.8}
DY_EM = {GRANDE: -0.021, SERIF: 0.0}
CAP = {GRANDE: 0.700, SERIF: 0.661}          # altura de mayúsculas / em (Pillow)
XS = 0.47                                    # la «x» de la serif / em, como en la maqueta
# la maqueta (en px de un cuadro de 720 de ancho; se escala con el cuadro)
ANCHO = 600.0 / 720.0                        # lo que puede ocupar la palabra grande del ancho
TOPE_G, TOPE_S = 0.30, 0.38                  # altura de mayúsculas máxima de la grande (× ANCHO) y la «x» de la serif (× mayúsculas de la grande)
CENTRO_Y = 0.58                              # el centro del bloque (fracción del alto, desde arriba)
MAX_PALABRAS, MAX_SEGUNDOS = 5, 3.0
ADELANTO, ANTES, COLA, MINIMO = 0.03, 0.02, 0.5, 0.6
# llevan a la palabra de la derecha (no cierran un trozo ni son la palabra grande): los de guion_planificador.DET y los posesivos largos
LLEVAN = G.DET | set('nuestra nuestro nuestras nuestros vuestra vuestro vuestras vuestros cada todo toda todos todas muy mas más our your their every'.split())


def _limpia(texto):
    return str(texto or '').replace('|', ' ').replace(';', ',').strip()


def _avance(par, texto, em):
    """Avance tipográfico (px) del texto con esa letra a ese em (Pillow)."""
    f = VC._fuente(par, 100)
    a100 = f.getlength(texto) if f is not None else len(texto) * 55.0
    return a100 * em / 100.0


def _trozos(pal, frase, forzados):
    """Parte una frase (índices) en trozos parejos de ≤ MAX_PALABRAS palabras y ≤ MAX_SEGUNDOS."""
    n = len(frase)
    partes = max(1, math.ceil(n / MAX_PALABRAS))
    while True:
        tam = [n // partes + (1 if i < n % partes else 0) for i in range(partes)]
        trozos, i = [], 0
        for t in tam:
            trozos.append(frase[i:i + t])
            i += t
        largo = max(pal[t[-1]]['fin'] - pal[t[0]]['t'] for t in trozos)
        if largo <= MAX_SEGUNDOS or partes >= n:
            break
        partes += 1
    return [t for t in trozos if t]


def _cuelga(w):
    """¿Esta palabra se queda colgando al final de un bloque? (artículos, preposiciones, posesivos y palabras vacías cortas: «la», «de», «se», «que»)"""
    return w['plano'] in LLEVAN or (w['plano'] in G.STOP and len(w['plano']) <= 3)


def _sin_colgantes(pal, trozos):
    """La palabra que cuelga al final de un bloque pasa al siguiente si la frase sigue (sin signo ni pausa) y allí cabe."""
    for j in range(len(trozos) - 1):
        while (len(trozos[j]) >= 2 and _cuelga(pal[trozos[j][-1]]) and not pal[trozos[j][-1]]['signo'] and len(trozos[j + 1]) < MAX_PALABRAS
               and pal[trozos[j + 1][0]]['t'] - pal[trozos[j][-1]]['fin'] < 0.35):
            trozos[j + 1].insert(0, trozos[j].pop())
    return [t for t in trozos if t]


def _clave(pal, trozo, forzados, primera):
    marcadas = [k for k in trozo if k in forzados]
    if marcadas:
        return marcadas[0]
    pts = {k: s for k, s in G.puntajes(pal, trozo, primera).items() if pal[k]['plano'] not in LLEVAN}
    if pts:
        return max(pts, key=lambda k: (pts[k], len(pal[k]['plano'])))
    return max(trozo, key=lambda k: len(pal[k]['plano']))


def maquetar(lineas, ancho_tl, alto_tl):
    """lineas [(texto, 'g'|'s')] (la grande una sola vez) -> [{'texto', 'par', 'size', 'cx', 'cy' (Fusion: y desde abajo), 'x0', 'x1', 'arriba',
    'abajo' (px desde arriba)}] con la maqueta de la propuesta."""
    base_w = min(float(ancho_tl), alto_tl * 9.0 / 16.0)
    esc = base_w / 720.0
    ancho = min(ANCHO * base_w, ZS.ancho(1.0, ancho_tl, alto_tl) * ancho_tl)    # v5.76: en vertical, el ancho de la zona segura (los iconos del reel)
    cx = ancho_tl / 2.0
    filas = []
    for texto, tipo in lineas:
        par = GRANDE if tipo == 'g' else SERIF
        filas.append({'texto': texto, 'tipo': tipo, 'par': par, 'w100': max(1.0, _avance(par, texto, 100.0))})
    grandes = [f for f in filas if f['tipo'] == 'g']
    for f in grandes:
        f['em'] = min(100.0 * ancho / f['w100'], TOPE_G * ancho / CAP[GRANDE])
        f['ancho'] = f['w100'] * f['em'] / 100.0
    cap_ref = max((f['em'] * CAP[GRANDE] for f in grandes), default=ancho * 0.2)
    ancho_g = max((f['ancho'] for f in grandes), default=ancho * 0.8)
    for f in filas:
        if f['tipo'] == 's':
            f['em'] = min(100.0 * max(0.74 * ancho_g, 0.6 * ancho) / f['w100'], TOPE_S * cap_ref / XS)
            f['ancho'] = f['w100'] * f['em'] / 100.0
    base, prev = 0.0, None
    for f in filas:                                     # líneas de base (px, desde arriba del bloque)
        if prev is None:
            base = f['em'] * CAP[GRANDE] if f['tipo'] == 'g' else f['em'] * XS * 1.2
        elif f['tipo'] == 'g' and prev['tipo'] == 'g':
            base = prev['base'] + f['em'] * CAP[GRANDE] + prev['em'] * CAP[GRANDE] * 0.10
        elif f['tipo'] == 'g':
            base = prev['base'] + f['em'] * CAP[GRANDE] * 0.80
        else:
            base = prev['base'] + f['em'] * XS * 0.95
        f['base'] = base
        prev = f
    alto = filas[-1]['base'] + 10.0 * esc
    y0 = alto_tl * CENTRO_Y - alto / 2.0
    y0 += ZS.meter_y(y0 / alto_tl, (y0 + alto) / alto_tl, ancho_tl, alto_tl) * alto_tl     # (v5.76: el bloque entero, dentro de la zona segura)
    izq, der = cx - ancho_g / 2.0, cx + ancho_g / 2.0
    sal = []
    for i, f in enumerate(filas):
        if f['tipo'] == 'g':
            x = cx - f['ancho'] / 2.0
        else:
            x = (izq + 6.0 * esc) if i == 0 else (der - f['ancho'] - 4.0 * esc)
        linea_base = y0 + f['base']
        par, em = f['par'], f['em']
        centro_y = linea_base - CAP[par] * em / 2.0 + DY_EM[par] * em
        size = em / (K_PX[par] * ancho_tl / 1080.0)
        sal.append({'texto': f['texto'], 'tipo': f['tipo'], 'par': par, 'size': size, 'cx': (x + f['ancho'] / 2.0) / ancho_tl, 'cy': 1.0 - centro_y / alto_tl,
                    'x0': x, 'x1': x + f['ancho'], 'arriba': linea_base - CAP[par] * em, 'cap': CAP[par] * em,
                    'abajo': linea_base + (0.0 if f['tipo'] == 'g' else 0.25 * em)})       # (la grande va en mayúsculas: sin descendentes)
    return sal


def codificar(textos, params, tablas):
    """El texto del Template de «v tipo»: 3 textos | 3 «size;cx;cy» | 3 tablas «t:f,t:f» (arriba, grande, abajo; vacíos donde no hay línea)."""
    ps = [(f'{p[0]:.5f};{p[1]:.5f};{p[2]:.5f}' if p else '') for p in params]
    ts = [','.join(f'{t:.3f}:{f:.4f}' for t, f in tab) for tab in tablas]
    return '|'.join([_limpia(t) for t in textos] + ps + ts)


def decodificar(texto):
    """Lo contrario de codificar: [arriba, grande, abajo], cada una {'texto', 'par', 'size', 'cx', 'cy', 'tabla': [(t, f)]} o None."""
    campos = (str(texto or '').split('|') + [''] * 9)[:9]
    sal = []
    for k, par in enumerate((SERIF, GRANDE, SERIF)):
        txt, p, tab = campos[k], campos[k + 3], campos[k + 6]
        try:
            size, cx, cy = (float(v) for v in p.split(';'))
        except ValueError:
            sal.append(None)
            continue
        pares = []
        for x in tab.split(','):
            if ':' in x:
                t, f = x.split(':', 1)
                try:
                    pares.append((float(t), float(f)))
                except ValueError:
                    pass
        sal.append({'texto': txt, 'par': par, 'size': size, 'cx': cx, 'cy': cy, 'tabla': pares} if txt.strip() else None)
    return sal


def _tabla(palabras, tiempos):
    """[(segundo, fracción de letras)] para revelar las palabras de una línea una a una (la fracción cae en el espacio que sigue a cada palabra:
    sirve igual si el Write On redondea hacia arriba o hacia abajo)."""
    linea = ' '.join(palabras)
    n = max(1, len(linea))
    tab, fin = [], 0
    for j, (w, t) in enumerate(zip(palabras, tiempos)):
        fin += len(w) + (1 if j else 0)
        f = 1.0 if j == len(palabras) - 1 else min(1.0, (fin + 0.5) / n)
        tab.append((max(0.0, t), f))
    return tab


def planificar(palabras, idioma='es', ancho_tl=1080, alto_tl=1920, ancla=None, mains=None, fin_video=None, **_otros):
    """palabras [{'word','start','end'}] -> {'cues': [...], 'plan': [...]} (el contrato de viral_planificador.planificar). `mains`: palabras (texto)
    o índices de la lista original forzados como palabra GRANDE (las «Principal» de Creativo). `ancla` no se usa: el bloque va siempre al centro."""
    unidas = VP.unir_fragmentos(palabras, idioma)
    pal = G._preparar(unidas)
    if not pal:
        return {'cues': [], 'plan': []}
    for w in pal:
        w['orig_real'] = sorted({o for jm in w.get('orig', ()) for o in unidas[jm].get('_o', [jm])})
    forzados = set()
    for m in (mains or []):
        if isinstance(m, int):
            forzados.update(k for k, w in enumerate(pal) if m in w['orig_real'])
        else:
            forzados.update(k for k, w in enumerate(pal) if w['plano'] == G._plano(str(m)))
    trozos = []
    for frase in G.frases(pal):
        trozos += _trozos(pal, frase, forzados)
    trozos = _sin_colgantes(pal, trozos)
    fin_total = float(fin_video) if fin_video else pal[-1]['fin'] + 1.5
    t0s = [max(0.0, pal[t[0]]['t'] - ADELANTO) for t in trozos]
    cues, plan = [], []
    for n, trozo in enumerate(trozos):
        t0 = t0s[n] if not cues else max(t0s[n], cues[-1]['end'])
        sig = t0s[n + 1] if n + 1 < len(trozos) else fin_total
        t1 = min(max(pal[trozo[-1]]['fin'] + COLA, t0 + MINIMO), max(sig, t0 + MINIMO))
        t1 = min(t1, fin_total) if fin_total > t0 + 0.2 else t1
        h = _clave(pal, trozo, forzados, n == 0)
        pos = trozo.index(h)
        grupos = [('s', trozo[:pos]), ('g', [h]), ('s', trozo[pos + 1:])]
        textos = {'arriba': '', 'grande': '', 'abajo': ''}
        lineas, palabras_de, roles = [], [], []
        for (tipo, ks), clave in zip(grupos, ('arriba', 'grande', 'abajo')):
            if not ks:
                continue
            ws = [_limpia(pal[k]['texto']) for k in ks]
            ws = [w.upper() for w in ws] if tipo == 'g' else [w.lower() for w in ws]
            textos[clave] = ' '.join(ws)
            lineas.append((textos[clave], tipo))
            palabras_de.append((clave, ks, ws))
        maq = maquetar(lineas, ancho_tl, alto_tl)
        por_clave = {clave: m for (clave, _ks, _ws), m in zip(palabras_de, maq)}
        params, tablas, lines = [], [], []
        for clave, rol in (('arriba', 'context'), ('grande', 'main'), ('abajo', 'complement')):
            m = por_clave.get(clave)
            if m is None:
                params.append(None)
                tablas.append([])
                continue
            _c, ks, ws = next(x for x in palabras_de if x[0] == clave)
            tiempos = [round(max(0.0, pal[k]['t'] - t0 - ANTES), 3) for k in ks]
            params.append((m['size'], m['cx'], m['cy']))
            tablas.append(_tabla(ws, tiempos))
            lines.append({'role': rol, 'text': ' '.join(ws), 'start': round(max(t0, pal[ks[0]]['t']), 3),
                          'dicho': ' '.join(_limpia(pal[k]['texto']) for k in ks)})       # (tal cual se dijo: la PRO del Tema 5 lo lee, edicion_pro_tema5.bloques)
        texto = codificar([textos['arriba'], textos['grande'], textos['abajo']], params, tablas)
        g = por_clave['grande']
        # la caja del bloque [arriba, abajo] (fracción del alto desde ARRIBA): la leen la PRO (la regla de la cara, «detrás de ti») y los emojis; los
        # runs no sirven para eso (el clip va centrado y sus líneas van dentro de su texto)
        caja = [round(min(m['arriba'] for m in maq) / alto_tl, 4), round(max(m['abajo'] for m in maq) / alto_tl, 4)]
        # 'codigo' = lo que va al Template del clip (el colocador lo prefiere a 'texto'); 'texto' = lo legible, para todo lo demás que lee los runs
        # (la PRO «Motions completo», las posiciones, los sonidos…: con el código enseñaba «Ventas|||0.29…»; GO real 06-11)
        legible = ' '.join(x for x in (textos['arriba'], textos['grande'], textos['abajo']) if x)
        run = {'k': CLIP, 't': round(t0, 3), 'fin': round(t1, 3), 'x': 0.5, 'y': 0.5, 'texto': legible, 'codigo': texto, 'size': round(g['size'], 4),
               't0_tipo': round(t0, 3)}
        lines.sort(key=lambda l: l['start'])
        # «detrás de ti» (edicion_pro.bloques_de_cues): la cabeza tapa media línea de ABAJO y solo si es la grande (con la serif debajo no va detrás)
        ultima = max(maq, key=lambda m: m['abajo'])
        cues.append({'start': round(t0, 3), 'end': round(t1, 3), 'plantilla': 'tipo', 'caja': caja, 'runs': [run], 'lines': lines,
                     'grande_abajo': ultima['tipo'] == 'g', 'linea_abajo': round(ultima['cap'] / alto_tl, 4)})
        plan.append({'i': n, 'tipo': 'tipo', 'heroe': textos['grande'], 'texto': ' '.join(l['text'] for l in lines), 't0': round(t0, 2), 't1': round(t1, 2)})
    return {'cues': cues, 'plan': plan}


def reajustar(cues):
    """Las tablas de tiempos del texto de un «v tipo» cuentan desde el inicio del CLIP (run['t0_tipo']). Si alguien lo hizo entrar más tarde (la
    mezcla de «Crea tu estilo» hace esperar un bloque: mezcla_planificador._retrasar), se corrigen para que cada palabra siga saliendo cuando se
    dice (lo que ya se había dicho sale al entrar). Devuelve los cues."""
    for c in cues or []:
        for r in c.get('runs') or []:
            if r.get('k') != CLIP or not isinstance(r.get('t0_tipo'), (int, float)) or not isinstance(r.get('t'), (int, float)):
                continue
            d = float(r['t']) - float(r['t0_tipo'])
            campos = str(r.get('codigo') or '').split('|')
            if abs(d) < 1e-4 or len(campos) != 9:
                continue
            for i in (6, 7, 8):
                pares = [x.split(':') for x in campos[i].split(',') if ':' in x]
                campos[i] = ','.join(f'{max(0.0, float(t) - d):.3f}:{f}' for t, f in pares)
            r['codigo'] = '|'.join(campos)
            r['t0_tipo'] = r['t']
    return cues
