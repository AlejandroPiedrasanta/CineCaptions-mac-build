# CineCaptions · By Cinema Productions
# 1_codigo/ambar_planificador.py — el Estilo 8 (v5.80): una línea pequeña y elegante en Montserrat ámbar, la clave en ExtraBold, palabra a palabra.
"""
ambar_planificador.py  (v5.80)
------------------------------
Pedido del usuario (con un TikTok de referencia: «crea el estilo 8»; eligió la propuesta A, fiel, y «acuérdate de la zona segura»):

  1. BLOQUES: las frases de guion_planificador partidas como el Tema 5 (tipo_planificador._trozos / _sin_colgantes: ≤ 5 palabras y ≤ 3 s, sin
     dejar un artículo colgando al final).
  2. UNA LÍNEA centrada por bloque: las palabras en Montserrat Regular ámbar claro («v ambar») y la CLAVE en Montserrat ExtraBold ámbar
     («v ambar clave»): la marcada como Principal en Creativo (`mains`) o la de más puntaje (tipo_planificador._clave); si es un nombre propio
     («Puerto Rico», «Ebenecer Auto») se lleva las palabras con mayúscula de al lado.
  3. TAMAÑO: el de la referencia («para el tráfico de Guatemala» ocupa el 60 % del ancho); si la línea no cabe en la zona segura, se achica.
     Línea de base al 70,5 % del alto (en horizontal, al 86 %), la caja dentro de la zona segura.
  4. CADA PALABRA entra cuando se dice (un pelín antes: su entrada sube, se enfoca y aparece en 7 fotogramas) y todas se van a la vez al acabar
     el bloque. run['sin_cola']: el colocador no le pone el mínimo de 0,45 s ni la cola (la última palabra, dicha justo antes del final, taparía
     el bloque siguiente). Mismo contrato que viral_planificador.planificar ({'cues', 'plan'}) y mismo colocador (place_kinetic_track).
"""
import guion_planificador as G
import tipo_planificador as TP
import viral_captions as VC
import viral_planificador as VP
import zona_segura as ZS

CLIP, CLIP_CLAVE = 'v ambar', 'v ambar clave'
FUENTE, FUENTE_CLAVE = ('Montserrat', 'Regular'), ('Montserrat', 'ExtraBold')    # = viral_elementos.AMBAR_FUENTE / AMBAR_FUENTE_CLAVE
K_PX = 707.1                     # px del em por unidad de «Size» a 1080 de ancho (Montserrat, medido en Resolve 21.2: tipo_planificador.K_PX)
CAP = 0.70                       # altura de mayúsculas / em (Pillow)
REFERENCIA, ANCHO_REF = ('para el tráfico de ', 'Guatemala'), 0.60
BASE_Y = {'v': 0.705, 'h': 0.86}  # la línea de base (fracción del alto)
ANCHO_MAX = 0.90                 # lo que puede ocupar la línea (en vertical, la zona segura)
ADELANTO, COLA, MINIMO, ANTES = 0.03, 0.45, 0.6, 0.06


def _avance(par, texto, em):
    f = VC._fuente(par, 100)
    return (f.getlength(texto) if f is not None else len(texto) * 58.0) * em / 100.0


def centro(par):
    """Lo que la línea de base queda por debajo del centro del Text+ (× em): (asc − desc) / 2 de hhea, como render_temas._centro."""
    f = VC._fuente(par, 200)
    if f is None:
        return 0.364
    asc, desc = f.getmetrics()
    return (asc - desc) / 400.0


def em_base(ancho_tl, alto_tl):
    """El em (px) de la referencia para este cuadro: la línea REFERENCIA ocupa ANCHO_REF del ancho de un vertical (en horizontal, del de un 9:16)."""
    base_w = min(float(ancho_tl), alto_tl * 9.0 / 16.0)
    w100 = _avance(FUENTE, REFERENCIA[0], 100.0) + _avance(FUENTE_CLAVE, REFERENCIA[1], 100.0)
    return 100.0 * ANCHO_REF * base_w / max(1.0, w100)


def _claves(pal, trozo, forzados, primera):
    marcadas = [k for k in trozo if k in forzados]
    if marcadas:
        return set(marcadas)
    h = TP._clave(pal, trozo, forzados, primera)
    claves = {h}
    if str(pal[h]['texto'])[:1].isupper():                  # un nombre propio de varias palabras va entero
        pos = trozo.index(h)
        for paso in (-1, 1):
            j = pos + paso
            while 0 <= j < len(trozo) and str(pal[trozo[j]]['texto'])[:1].isupper() and not (j == 0 and paso == -1 and primera):
                claves.add(trozo[j])
                j += paso
    return claves


def planificar(palabras, idioma='es', ancho_tl=1080, alto_tl=1920, ancla=None, mains=None, fin_video=None, **_otros):
    """palabras [{'word','start','end'}] -> {'cues': [...], 'plan': [...]}. `mains`: palabras (texto) o índices de la lista original forzados como
    clave (las «Principal» de Creativo). `ancla` no se usa: la línea va siempre abajo, dentro de la zona segura."""
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
        trozos += TP._trozos(pal, frase, forzados)
    trozos = TP._sin_colgantes(pal, trozos)
    fin_total = float(fin_video) if fin_video else pal[-1]['fin'] + 1.5
    horizontal = ancho_tl > alto_tl
    em0 = em_base(ancho_tl, alto_tl)
    maximo = ZS.ancho(ANCHO_MAX, ancho_tl, alto_tl) * ancho_tl
    base_y = BASE_Y['h' if horizontal else 'v'] * alto_tl
    t0s = [max(0.0, pal[t[0]]['t'] - ADELANTO) for t in trozos]
    cues, plan = [], []
    for n, trozo in enumerate(trozos):
        t0 = t0s[n] if not cues else max(t0s[n], cues[-1]['end'])
        sig = t0s[n + 1] if n + 1 < len(trozos) else fin_total
        t1 = min(max(pal[trozo[-1]]['fin'] + COLA, t0 + MINIMO), max(sig, t0 + MINIMO))
        t1 = min(t1, fin_total) if fin_total > t0 + 0.2 else t1
        claves = _claves(pal, trozo, forzados, n == 0)
        textos = [str(pal[k]['texto']).strip() for k in trozo]
        pares = [FUENTE_CLAVE if k in claves else FUENTE for k in trozo]
        em = em0
        anchos = [_avance(p, t, em) for p, t in zip(pares, textos)]
        esp = _avance(FUENTE, ' ', em)
        total = sum(anchos) + esp * (len(anchos) - 1)
        if total > maximo:                                  # no cabe: la línea entera se achica
            f = maximo / total
            em, anchos, esp, total = em * f, [a * f for a in anchos], esp * f, maximo
        cap = CAP * em
        base = base_y + ZS.meter_y((base_y - cap * 1.15) / alto_tl, (base_y + 0.25 * em) / alto_tl, ancho_tl, alto_tl) * alto_tl
        x = ancho_tl / 2.0 - total / 2.0
        size = em / (K_PX * ancho_tl / 1080.0)
        runs = []
        for k, txt, par, a in zip(trozo, textos, pares, anchos):
            r = {'k': CLIP_CLAVE if k in claves else CLIP, 't': round(min(max(t0, pal[k]['t'] - ANTES), t1 - 0.1), 3), 'fin': round(t1, 3),
                 'x': round((x + a / 2.0) / ancho_tl, 5), 'y': round((base - centro(par) * em) / alto_tl, 5), 'texto': txt, 'size': round(size, 4),
                 'sin_cola': True}
            if k in claves:
                r['principal'] = True
            runs.append(r)
            x += a + esp
        caja = [round((base - cap * 1.15) / alto_tl, 4), round((base + 0.25 * em) / alto_tl, 4)]
        lines = [{'role': 'main' if k in claves else 'base', 'text': t, 'start': round(max(t0, pal[k]['t']), 3)} for k, t in zip(trozo, textos)]
        cues.append({'start': round(t0, 3), 'end': round(t1, 3), 'plantilla': 'ambar', 'caja': caja, 'runs': runs, 'lines': lines,
                     'grande_abajo': True, 'linea_abajo': round(cap / alto_tl, 4)})
        heroe = ' '.join(t for k, t in zip(trozo, textos) if k in claves)
        plan.append({'i': n, 'tipo': 'ambar', 'heroe': heroe, 'texto': ' '.join(textos), 't0': round(t0, 2), 't1': round(t1, 2)})
    return {'cues': cues, 'plan': plan}
