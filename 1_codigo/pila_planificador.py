# CineCaptions · By Cinema Productions
# 1_codigo/pila_planificador.py — el Estilo 4 (v5.82): la pila de tres alturas de la referencia del usuario: arriba lo dicho antes de la clave en
# Inter Bold blanca, la CLAVE grande en Inter ExtraBold lima con brillo y debajo, a la derecha, lo que sigue.
"""
pila_planificador.py  (v5.82)
-----------------------------
Pedido del usuario («crea este estilo… y reemplázalo por el Estilo 4»; «date cuenta de que en el ejemplo las palabras tienen arriba, en medio y
abajo»). Todo MEDIDO en 6 bloques de la referencia (1080×1920):

  1. BLOQUES: las frases partidas en trozos parejos de ≤ 7 palabras y ≤ 3 s (la referencia lleva 4-7: «If the Prospects have to meet you»); la
     palabra que cuelga al final pasa al siguiente (como tipo_planificador).
  2. TRES ALTURAS: arriba lo dicho ANTES de la clave (si detrás vienen 3 o más, sus 2 primeras van arriba a la derecha: «If the
     … have to / Prospects / meet you»); en medio la CLAVE —la Principal de Creativo o tipo_planificador._clave; un nombre propio de varias
     palabras va entero («Puerto Rico») y un posesivo o un «más» se le pega («Your plate», «Más grande»)— con mayúscula inicial, llenando el
     ancho de la zona segura sin pasar de 0,066 del alto en mayúsculas; y abajo, a la derecha (acaba 0,10 em de la grande antes de su borde), lo de
     DESPUÉS.
  3. CADA LÍNEA PEQUEÑA con su letra: la que la hace medir 0,38 del ancho de la grande (0,62 la que remata en lima), entre 0,28 y 0,76 (0,90)
     de la letra grande: una corta sale grande («to» 0,76) y una larga pequeña («you are unsure» 0,30).
  4. La última de abajo va en LIMA si la línea tiene 1 o 2 palabras y remata con una de contenido («your value», «you out»; «meet you», no; y la
     previa aprobada: «… / Especiales / especiales»).
  5. Las pequeñas se apoyan en la SILUETA de la grande (su tinta, columna a columna): se meten en los huecos de sus minúsculas, suben sobre
     mayúsculas y astas y bajan bajo una «p» o una «g»; nunca se pisan.
  6. Cada palabra entra cuando se dice (2 fotogramas, sin desenfoque ni rebote: viral_elementos.comp_pila) y el bloque entero se va de golpe
     (run['sin_cola']: sin cola ni mínimo, como los Estilos 8 y 9).
El espaciado de letras de Text+ SUMA (esp − 1) × 1,53 em por letra (render_temas.K_ESP_TEXTPLUS): 0,97 = −0,046 em (la grande de la referencia,
−0,045) y 0,98 = −0,031 (las pequeñas, −0,03).
"""
import math

import numpy as np
from PIL import Image, ImageDraw

import guion_planificador as G
import tipo_planificador as TP
import viral_captions as VC
import viral_planificador as VP
import zona_segura as ZS
from ambar_planificador import centro

CLIP_G, CLIP_P, CLIP_L = 'v pila', 'v pila peq', 'v pila lima'
GRANDE, PEQ = ('Inter 28pt', 'ExtraBold'), ('Inter 24pt', 'Bold')     # = viral_elementos.PILA_GRANDE / PILA_PEQ
ESP_G, ESP_P = 0.97, 0.98            # CharacterSpacing de Text+ (= viral_elementos.PILA_ESP)
K_ESP = 1.53                         # (esp − 1) × K_ESP em por letra (render_temas.K_ESP_TEXTPLUS, medido en Resolve)
K_PX = VC.K_PX                       # px del em por unidad de «Size» a 1080 de ancho (Inter, medido en Resolve: 691)
CAP = 0.728                          # mayúsculas / em de Inter 28pt (viral_captions.CAP)
CAP_MAX = 0.066                      # la grande no pasa de esta altura de mayúsculas (fracción del alto de un vertical)
PEQ_ANCHO, PEQ_MIN, PEQ_MAX = 0.38, 0.28, 0.76
PEQ_ANCHO_ENF, PEQ_MAX_ENF = 0.62, 0.90
SANGRIA, DER_ARRIBA, DER_ABAJO = 0.70, -0.87, -0.10      # × em de la grande
AIRE_G = 0.08                        # aire de más entre las palabras de la grande (em; medido 0,24-0,31 de hueco)
HOLGURA = 0.025                      # lo mínimo entre la tinta de una pequeña y la de la grande (× em de la grande)
BASE_Y = {'v': 0.575, 'h': 0.72}     # la línea de base de la grande (fracción del alto; la referencia: 0,571-0,580)
MAX_PALABRAS, MAX_SEGUNDOS = 7, 3.0
POS_ULTIMA, POS_PRIMERA = 0.70, 0.60     # cuánto pesa la clave si es la última o la primera del bloque (la referencia la deja en medio: 0 de 7 primeras)
UNIR_PAUSA = 1.2                         # una frase de una palabra se une a la siguiente si esta empieza antes de esto (s)
ADELANTO, COLA, MINIMO, ANTES = 0.03, 0.45, 0.6, 0.03
PEGAN = set('tu tus su sus mi mis nuestra nuestro nuestras nuestros vuestra vuestro vuestras vuestros más mas muy '
            'your my our their his her its more most very ton ta tes votre vos notre nos seu sua seus suas meu minha '
            'dein deine sein seine mein meine unser unsere il tuo tua'.split())


# ------------------------------------------------------------------------------------------------------------------ medidas
def _fuente(par, px):
    return VC._fuente(par, max(1, int(round(px))))


def avance(texto, par, em, esp):
    """Lo que ocupa una palabra en Text+ (px): su avance tipográfico menos lo que quita el espaciado entre cada dos letras."""
    f = _fuente(par, 100)
    a = (f.getlength(texto) if f is not None else len(texto) * 58.0) * em / 100.0
    return a + (esp - 1.0) * K_ESP * em * max(0, len(texto) - 1)


def _ancho_linea(textos, par, em, esp, aire=0.0):
    esp_px = avance(' ', par, em, 1.0) + aire * em
    return sum(avance(t, par, em, esp) for t in textos) + esp_px * max(0, len(textos) - 1)


def _dibujar(d, x, base, texto, f, em, esp):
    """Como Text+: letra a letra con su avance (y el interletraje de la fuente) y el espaciado sumado entre cada dos."""
    for i, ch in enumerate(texto):
        d.text((x, base), ch, font=f, fill=255, anchor='ls')
        x += f.getlength(ch) + (esp - 1.0) * K_ESP * em
        if i + 1 < len(texto):
            x += f.getlength(texto[i:i + 2]) - f.getlength(texto[i]) - f.getlength(texto[i + 1])


def _perfil(items, caja, red):
    """Por columna de la caja (x0, y0, x1, y1, en px del cuadro) la fila de arriba y la de abajo de la tinta de las palabras [(texto, par, em, esp,
    x, base)], en px del cuadro; dibujado a la escala `red` (≤ 1) para que no pese."""
    x0, y0, x1, y1 = caja
    w, h = max(2, int(math.ceil((x1 - x0) * red))), max(2, int(math.ceil((y1 - y0) * red)))
    im = Image.new('L', (w, h), 0)
    d = ImageDraw.Draw(im)
    for texto, par, em, esp, x, base in items:
        f = _fuente(par, em * red)
        if f is not None:
            _dibujar(d, (x - x0) * red, (base - y0) * red, texto, f, em * red, esp)
    m = np.asarray(im) > 100
    hay = m.any(axis=0)
    arriba = np.where(hay, m.argmax(axis=0), h).astype(float) / red + y0
    abajo = np.where(hay, h - 1 - m[::-1].argmax(axis=0), -1).astype(float) / red + y0
    return hay, arriba, abajo


def _letra_peq(texto, em_g, wg, tope_ancho, enfasis=False):
    a, tope = (PEQ_ANCHO_ENF, PEQ_MAX_ENF) if enfasis else (PEQ_ANCHO, PEQ_MAX)
    w1 = max(1e-6, _ancho_linea(texto.split(' '), PEQ, 1.0, ESP_P))
    em = max(PEQ_MIN * em_g, min(tope * em_g, a * wg / w1))
    return min(em, tope_ancho / w1)                                    # (y nunca más ancha que lo que le toca)


# ------------------------------------------------------------------------------------------------------------------ bloques
def _trozos(pal, frase):
    n = len(frase)
    partes = max(1, math.ceil(n / MAX_PALABRAS))
    while True:
        tam = [n // partes + (1 if i < n % partes else 0) for i in range(partes)]
        trozos, i = [], 0
        for t in tam:
            trozos.append(frase[i:i + t])
            i += t
        if max(pal[t[-1]]['fin'] - pal[t[0]]['t'] for t in trozos) <= MAX_SEGUNDOS or partes >= n:
            break
        partes += 1
    return [t for t in trozos if t]


def _sin_colgantes(pal, trozos):
    for j in range(len(trozos) - 1):
        while (len(trozos[j]) >= 2 and TP._cuelga(pal[trozos[j][-1]]) and not pal[trozos[j][-1]]['signo'] and len(trozos[j + 1]) < MAX_PALABRAS
               and pal[trozos[j + 1][0]]['t'] - pal[trozos[j][-1]]['fin'] < 0.35):
            trozos[j + 1].insert(0, trozos[j].pop())
    return [t for t in trozos if t]


def _clave(pal, trozo, primera):
    """La de más puntaje (tipo_planificador._clave), pero como la referencia, que la deja EN MEDIO para que haya línea de abajo (6 de 7 bloques:
    «to / Understand / your value»): en un bloque de 3 o más, la última pesa ×0,7 y la primera ×0,6."""
    pts = {k: s for k, s in G.puntajes(pal, trozo, primera).items() if pal[k]['plano'] not in TP.LLEVAN}
    if not pts:
        return max(trozo, key=lambda k: len(pal[k]['plano']))
    n = len(trozo)

    def peso(k):
        i = trozo.index(k)
        f = POS_ULTIMA if (n >= 3 and i == n - 1) else (POS_PRIMERA if (n >= 3 and i == 0) else 1.0)
        return (pts[k] * f, len(pal[k]['plano']))
    return max(pts, key=peso)


def _frases(pal):
    """Las frases de guion_planificador, pero una de UNA palabra se une a la siguiente si sigue enseguida y caben (la referencia empieza «If» sola
    arriba y sigue el bloque: «If the Prospects have to meet you»)."""
    out = []
    for fr in G.frases(pal):
        if out and len(out[-1]) == 1 and len(out[-1]) + len(fr) <= MAX_PALABRAS and pal[fr[0]]['t'] - pal[out[-1][-1]]['fin'] < UNIR_PAUSA:
            out[-1] = out[-1] + list(fr)
        else:
            out.append(list(fr))
    return out


def _grande(pal, trozo, forzados, primera):
    """Los índices (seguidos) de la grande: la clave, con el nombre propio entero y el posesivo o «más» que la lleva delante."""
    marcadas = [k for k in trozo if k in forzados]
    if marcadas:
        a, b = trozo.index(marcadas[0]), trozo.index(marcadas[-1])
        return trozo[a:b + 1] if b - a <= 1 else [marcadas[0]]
    h = _clave(pal, trozo, primera)
    pos = trozo.index(h)
    a = b = pos
    if str(pal[h]['texto'])[:1].isupper():                             # un nombre propio de varias palabras va entero (máx. 2)
        if b + 1 < len(trozo) and str(pal[trozo[b + 1]]['texto'])[:1].isupper():
            b += 1
        elif a - 1 >= 0 and str(pal[trozo[a - 1]]['texto'])[:1].isupper() and not (a - 1 == 0 and primera):
            a -= 1
    if a == b and a - 1 >= 0 and pal[trozo[a - 1]]['plano'] in PEGAN:  # «Your plate», «Más grande»
        a -= 1
    return trozo[a:b + 1]


def _remata(w):
    """¿La última palabra de abajo dice algo (va en lima)? Ni vacía ni muy corta (como editorial_planificador._serif_final)."""
    return w['plano'] not in G.STOP and w['plano'] not in TP.LLEVAN and len(w['plano']) >= 4


def _texto(pal, k):
    return str(pal[k]['texto']).strip().strip(',.;:!?¿¡…"«»')


# ------------------------------------------------------------------------------------------------------------------ maqueta
def maquetar(pal, trozo, gr, ancho_tl, alto_tl):
    """La pila de un bloque: [(fila, k, texto, par, em, esp, x (izquierda), base, lima)] en px del cuadro."""
    horizontal = ancho_tl > alto_tl
    base_w = min(float(ancho_tl), alto_tl * 9.0 / 16.0)
    zx0, zx1 = ZS.limites_x(ancho_tl, alto_tl, defecto=(0.04, 0.96))
    if not horizontal:                                                  # el brillo lima y la sombra sobresalen ~20 px de la letra: la TINTA dentro de la zona
        zx0, zx1 = zx0 + ZS.AIRE_TINTA, zx1 - ZS.AIRE_TINTA
    w_max = (zx1 - zx0) * ancho_tl if not horizontal else 0.50 * ancho_tl
    base_g = BASE_Y['h' if horizontal else 'v'] * alto_tl
    pos_a, pos_b = trozo.index(gr[0]), trozo.index(gr[-1])
    a_izq, debajo = trozo[:pos_a], trozo[pos_b + 1:]
    a_der = []
    if len(debajo) >= 3:                                                # (también sin nada a la izquierda: «Ventas / especiales para / clientes …»)
        a_der, debajo = debajo[:2], debajo[2:]
    g_txt = [_texto(pal, k) for k in gr]
    g_txt[0] = g_txt[0][:1].upper() + g_txt[0][1:]
    w1 = max(1e-6, _ancho_linea(g_txt, GRANDE, 1.0, ESP_G, AIRE_G))
    em_g = min(w_max / w1, CAP_MAX * base_w * 16.0 / 9.0 / CAP)
    wg = w1 * em_g
    xg = ancho_tl / 2.0 - wg / 2.0
    cap_g = CAP * em_g
    filas = []
    x = xg
    esp_g = avance(' ', GRANDE, em_g, 1.0) + AIRE_G * em_g
    for k, t in zip(gr, g_txt):
        filas.append(('grande', k, t, GRANDE, em_g, ESP_G, x, base_g, True))
        x += avance(t, GRANDE, em_g, ESP_G) + esp_g
    red = min(1.0, 540.0 / ancho_tl)
    caja = (0.0, base_g - 3.0 * cap_g, float(ancho_tl), base_g + 3.0 * cap_g)
    hay_g, arr_g, aba_g = _perfil([(t, par, em, esp, xx, b) for _f, _k, t, par, em, esp, xx, b, _l in filas], caja, red)
    holgura, b0 = HOLGURA * em_g, base_g
    if a_izq or a_der:                                                  # arriba: una sola letra para toda la línea
        textos = [_texto(pal, k) for k in a_izq + a_der]
        em_a = _letra_peq(' '.join(textos), em_g, wg, wg)
        w_i = _ancho_linea([_texto(pal, k) for k in a_izq], PEQ, em_a, ESP_P)
        w_d = _ancho_linea([_texto(pal, k) for k in a_der], PEQ, em_a, ESP_P)
        esp_a = avance(' ', PEQ, em_a, 1.0)
        fila_a, x = [], max(xg, min(xg + SANGRIA * em_g, xg + wg - w_i))
        for k in a_izq:
            t = _texto(pal, k)
            fila_a.append(('arriba', k, t, PEQ, em_a, ESP_P, x, b0, False))
            x += avance(t, PEQ, em_a, ESP_P) + esp_a
        if a_der:
            x_fin = min(xg + wg, max(xg + wg + DER_ARRIBA * em_g, (x - esp_a) + 0.5 * em_g + w_d))
            x = x_fin - w_d
            for k in a_der:
                t = _texto(pal, k)
                fila_a.append(('arriba', k, t, PEQ, em_a, ESP_P, x, b0, False))
                x += avance(t, PEQ, em_a, ESP_P) + esp_a
        hay, _arr, aba = _perfil([(t, par, em, esp, xx, b) for _f, _k, t, par, em, esp, xx, b, _l in fila_a], caja, red)
        c = hay & hay_g
        base_a = float((arr_g[c] - (aba[c] - b0) - holgura).min()) if c.any() else base_g - cap_g
        base_a = max(base_g - 1.30 * cap_g, min(base_a, base_g - cap_g + 0.28 * cap_g))   # (ni más honda que la referencia ni flotando)
        filas += [(f, k, t, par, em, esp, xx, base_a, l) for f, k, t, par, em, esp, xx, _b, l in fila_a]
    if debajo:
        textos = [_texto(pal, k) for k in debajo]
        lima = len(debajo) <= 2 and _remata(pal[debajo[-1]])
        tope = (zx1 - zx0) * ancho_tl - 4
        em_b = _letra_peq(' '.join(textos), em_g, wg, tope, enfasis=lima)
        w_b = _ancho_linea(textos, PEQ, em_b, ESP_P)
        x = max(zx0 * ancho_tl + 2, min(zx1 * ancho_tl - 2, xg + wg + DER_ABAJO * em_g) - w_b)
        esp_b = avance(' ', PEQ, em_b, 1.0)
        fila_b = []
        for j, k in enumerate(debajo):
            t = textos[j]
            fila_b.append(('abajo', k, t, PEQ, em_b, ESP_P, x, b0, lima and j == len(debajo) - 1))
            x += avance(t, PEQ, em_b, ESP_P) + esp_b
        hay, arr, _aba = _perfil([(t, par, em, esp, xx, b) for _f, _k, t, par, em, esp, xx, b, _l in fila_b], caja, red)
        c = hay & hay_g
        base_b = float((aba_g[c] - (arr[c] - b0) + holgura).max()) if c.any() else base_g + 0.70 * em_b
        base_b = min(base_g + 1.10 * em_b, max(base_b, base_g + 0.30 * em_b))
        filas += [(f, k, t, par, em, esp, xx, base_b, l) for f, k, t, par, em, esp, xx, _b, l in fila_b]
    return filas


# ------------------------------------------------------------------------------------------------------------------ plan
def planificar(palabras, idioma='es', ancho_tl=1080, alto_tl=1920, ancla=None, mains=None, fin_video=None, **_otros):
    """palabras [{'word','start','end'}] -> {'cues': [...], 'plan': [...]} (el contrato de viral_planificador.planificar). `ancla` no se usa: la
    pila va siempre a media altura (como la referencia), dentro de la zona segura."""
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
    for frase in _frases(pal):
        trozos += _trozos(pal, frase)
    trozos = _sin_colgantes(pal, trozos)
    fin_total = float(fin_video) if fin_video else pal[-1]['fin'] + 1.5
    t0s = [max(0.0, pal[t[0]]['t'] - ADELANTO) for t in trozos]
    cues, plan = [], []
    for n, trozo in enumerate(trozos):
        t0 = t0s[n] if not cues else max(t0s[n], cues[-1]['end'])
        sig = t0s[n + 1] if n + 1 < len(trozos) else fin_total
        t1 = min(max(pal[trozo[-1]]['fin'] + COLA, t0 + MINIMO), max(sig, t0 + MINIMO))
        t1 = min(t1, fin_total) if fin_total > t0 + 0.2 else t1
        gr = _grande(pal, trozo, forzados, n == 0)
        filas = maquetar(pal, trozo, gr, ancho_tl, alto_tl)
        runs, lines = [], []
        for fila, k, t, par, em, esp, x, base, lima in sorted(filas, key=lambda f: pal[f[1]]['t']):
            clip = CLIP_G if fila == 'grande' else (CLIP_L if lima else CLIP_P)
            runs.append({'k': clip, 't': round(min(max(t0, pal[k]['t'] - ANTES), t1 - 0.1), 3), 'fin': round(t1, 3),
                         'x': round((x + avance(t, par, em, esp) / 2.0) / ancho_tl, 5), 'y': round((base - centro(par) * em) / alto_tl, 5),
                         'texto': t, 'size': round(em / (K_PX * ancho_tl / 1080.0), 4), 'sin_cola': True,
                         **({'principal': True} if fila == 'grande' else {})})
        for fila, rol in (('arriba', 'context'), ('grande', 'main'), ('abajo', 'complement')):
            sel = [f for f in filas if f[0] == fila]
            if sel:
                lines.append({'role': rol, 'text': ' '.join(f[2] for f in sel), 'start': round(max(t0, min(pal[f[1]]['t'] for f in sel)), 3)})
        top = min(f[7] - CAP * f[4] for f in filas)
        bottom = max(f[7] + 0.22 * f[4] for f in filas)
        abajo = [f for f in filas if f[0] == 'abajo']
        lines.sort(key=lambda l: l['start'])
        heroe = ' '.join(f[2] for f in filas if f[0] == 'grande')
        cues.append({'start': round(t0, 3), 'end': round(t1, 3), 'plantilla': 'pila4', 'caja': [round(top / alto_tl, 4), round(bottom / alto_tl, 4)],
                     'runs': runs, 'lines': lines, 'grande_abajo': not abajo,
                     'linea_abajo': round((CAP * abajo[0][4] if abajo else CAP * filas[0][4]) / alto_tl, 4)})
        plan.append({'i': n, 'tipo': 'pila4', 'heroe': heroe, 'texto': ' '.join(l['text'] for l in lines), 't0': round(t0, 2), 't1': round(t1, 2)})
    return {'cues': cues, 'plan': plan}
