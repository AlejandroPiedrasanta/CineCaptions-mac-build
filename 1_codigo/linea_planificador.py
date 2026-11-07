# CineCaptions · By Cinema Productions
# 1_codigo/linea_planificador.py — el Tema 3 (v5.75): toda la frase en UNA línea de mayúsculas condensadas y una caja negra que salta de palabra en palabra.
"""
linea_planificador.py  (v5.75)
------------------------------
El Tema 3 de la página Tema y de GO (referencia del usuario «ESTE ES EL ACABADO FINO»; pedido: «reemplaza el tema 3 por este estilo sin eliminar de
crea tu estilo los captions del tema 3»). Los looks de antes del Tema 3 (pila, select, shatter, drag, corte, giro 3D, resaltado) siguen en
viral_planificador y «Crea tu estilo» los usa igual; este planificador solo lo llama GO cuando el pack es el del Tema 3.

  1. FRASES: las de guion_planificador (signo fuerte, pausa…), cada una partida en LÍNEAS que caben a lo ancho (≤ ANCHO_MAX del cuadro con la letra a
     su tamaño), de ≤ MAX_PALABRAS palabras y ≤ MAX_SEGUNDOS de voz. Sin palabra grande ni efectos.
  2. CLIPS del pack (mismo colocador y mismo .json que VIRAL): cada palabra es un «v linea» desde que empieza la línea hasta que acaba (la frase se ve
     entera, como en la referencia); la que suena lleva encima un «v linea activa» (la palabra con la caja negra detrás) desde que se dice hasta que
     empieza la siguiente, con run['exacto'] (el colocador no le pone el mínimo de 0,45 s ni la cola: dos cajas nunca se ven a la vez).
  3. TAMAÑO: mayúsculas de CAP_REFERENCIA del lado de referencia (60 px a 1920, como la referencia); si la línea no cabe, se achica.
"""
import guion_planificador as G
import viral_captions as VC
import viral_planificador as VP
import zona_segura as ZS

CLIP, CLIP_ACTIVA = 'v linea', 'v linea activa'
CLIP_ACTIVA_CREA = 'v linea activa azul'   # el look 't3:linea' de «Crea tu estilo»: caja azul (su color = el «color principal»)
FUENTE = ('Barlow Semi Condensed', 'Bold')
ESP = 0.975                           # = viral_elementos.LINEA_ESP (el CharacterSpacing del Text+)
K_PX = 714.0                          # px del em por unidad de «Size» a 1080 px de ancho (render de Resolve: «HHHH» a Size 0,2 → mayúsculas de 100 px)
RADIO_CAJA = 0.09                     # esquinas de la caja × su alto: sutiles, como la referencia (el usuario: «no es un óvalo»)
CAP_EM = 0.70                         # altura de mayúsculas / em de la Barlow Semi Condensed (Pillow: «H» 700/1000)
CAP_REFERENCIA = 0.031                # mayúsculas / lado de referencia (60 px a 1920)
ANCHO_MAX = 0.90                      # lo que puede ocupar la línea del ancho del cuadro (la referencia: 0,84 con 5 palabras); en vertical, la zona segura
HUECO = 0.60                          # espacio entre palabras × altura de mayúsculas (la referencia: 0,62)
CAJA_LADO = 0.36                      # lo que la caja de la palabra activa sobresale a cada lado × altura de mayúsculas (viral_elementos: sin Extend, 0,36)
MAX_PALABRAS, MAX_SEGUNDOS = 6, 3.2
ADELANTO, COLA, MINIMO = 0.03, 0.45, 0.6
K_ESP_TEXTPLUS = 1.53                 # Text+ SUMA (CharacterSpacing − 1) × 1,53 em por letra (render_temas.K_ESP_TEXTPLUS)


def _visible(texto):
    return str(texto).strip().upper()


def _ancho(texto, size, ancho_tl):
    """Ancho (px) de la palabra con ese «Size» de Text+ (Pillow con la misma letra + lo que aprieta el CharacterSpacing)."""
    em = size * K_PX * ancho_tl / 1080.0
    f = VC._fuente(FUENTE, em)
    avance = f.getlength(texto) if f is not None else len(texto) * em * 0.48
    return avance + (ESP - 1.0) * K_ESP_TEXTPLUS * em * max(0, len(texto) - 1)


def _size_para_cap(cap_px, ancho_tl):
    return cap_px / CAP_EM / (K_PX * ancho_tl / 1080.0)


def _lineas_de_frase(pal, frase, size, ancho_tl, ancho_max=ANCHO_MAX):
    """Parte una frase (índices) en líneas que caben, de ≤ MAX_PALABRAS y ≤ MAX_SEGUNDOS."""
    maximo = ancho_max * ancho_tl
    cap_px = size * K_PX * ancho_tl / 1080.0 * CAP_EM
    lineas, actual, ancho = [], [], 0.0
    for k in frase:
        w = _ancho(_visible(pal[k]['texto']), size, ancho_tl)
        extra = (HUECO * cap_px if actual else 0.0) + w
        largo = (pal[k]['fin'] - pal[actual[0]]['t']) if actual else 0.0
        if actual and (ancho + extra > maximo or len(actual) >= MAX_PALABRAS or largo > MAX_SEGUNDOS):
            lineas.append(actual)
            actual, ancho = [], 0.0
            extra = w
        actual.append(k)
        ancho += extra
    if actual:
        lineas.append(actual)
    # sin una palabra sola al final si la anterior puede cederle una (se ve mejor «SE VEAN» que «VEAN»)
    if len(lineas) >= 2 and len(lineas[-1]) == 1 and len(lineas[-2]) >= 3:
        lineas[-1].insert(0, lineas[-2].pop())
    return lineas


def planificar(palabras, idioma='es', ancho_tl=1080, alto_tl=1920, ancla='bajo', mains=None, fin_video=None, clip_activa=CLIP_ACTIVA, **_otros):
    """palabras [{'word','start','end'}] -> {'cues': [...], 'plan': [...]} (el contrato de viral_planificador.planificar; `mains` no se usa: no hay
    palabra grande)."""
    unidas = VP.unir_fragmentos(palabras, idioma)
    pal = G._preparar(unidas)
    if not pal:
        return {'cues': [], 'plan': []}
    horizontal = ancho_tl > alto_tl
    tabla = VP.ANCLAS_HORIZONTAL if horizontal else VP.ANCLAS
    y = tabla.get(ancla, tabla['bajo']) if not isinstance(ancla, (int, float)) else float(ancla)
    ref = VC.lado_de_referencia(ancho_tl, alto_tl)
    size0 = _size_para_cap(CAP_REFERENCIA * ref, ancho_tl)
    # v5.76 (zona segura): en vertical la línea cabe entre los iconos del reel y el borde (zona_segura.ANCHO): se parte antes, con la misma letra
    ancho_max = ZS.ancho(ANCHO_MAX, ancho_tl, alto_tl)
    if ZS.vertical(ancho_tl, alto_tl):                    # (contando la caja de la primera y la última palabra, que sobresale del texto)
        ancho_max -= 2 * CAJA_LADO * size0 * K_PX / 1080.0 * CAP_EM
    lineas = []
    for frase in G.frases(pal):
        lineas += _lineas_de_frase(pal, frase, size0, ancho_tl, ancho_max)
    fin_total = float(fin_video) if fin_video else pal[-1]['fin'] + 1.5
    # tiempos: cada línea desde su primera palabra (un pelín antes) hasta un poco después de la última, sin pisar a la siguiente
    t0s = [max(0.0, pal[l[0]]['t'] - ADELANTO) for l in lineas]
    cues, plan = [], []
    for n, l in enumerate(lineas):
        t0 = t0s[n] if not cues else max(t0s[n], cues[-1]['end'])
        sig = t0s[n + 1] if n + 1 < len(lineas) else fin_total
        t1 = min(max(pal[l[-1]]['fin'] + COLA, t0 + MINIMO), max(sig, t0 + MINIMO))
        t1 = min(t1, fin_total) if fin_total > t0 + 0.2 else t1
        textos = [_visible(pal[k]['texto']) for k in l]
        # tamaño: el de referencia; si no cabe (una palabra muy larga), se achica la línea entera
        size = size0
        cap_px = size * K_PX * ancho_tl / 1080.0 * CAP_EM
        anchos = [_ancho(tx, size, ancho_tl) for tx in textos]
        total = sum(anchos) + HUECO * cap_px * (len(anchos) - 1)
        if total > ancho_max * ancho_tl:
            f = ancho_max * ancho_tl / total
            size *= f
            cap_px *= f
            anchos = [a * f for a in anchos]
            total *= f
        x = 0.5 * ancho_tl - total / 2.0
        alto_px = cap_px * 2.1
        y_l = y + ZS.meter_y(y - alto_px / 2 / alto_tl, y + alto_px / 2 / alto_tl, ancho_tl, alto_tl)     # (v5.76: la caja, dentro de la zona)
        runs, activas = [], []
        for j, (k, tx, a) in enumerate(zip(l, textos, anchos)):
            cx = (x + a / 2.0) / ancho_tl
            runs.append({'k': CLIP, 't': round(t0, 3), 'fin': round(t1, 3), 'x': round(cx, 5), 'y': round(y_l, 5), 'texto': tx, 'size': round(size, 4)})
            ini = max(t0, pal[k]['t'])
            fin = max(t0, pal[l[j + 1]]['t']) if j + 1 < len(l) else t1
            if fin - ini >= 0.03:
                activas.append({'k': clip_activa, 't': round(ini, 3), 'fin': round(fin, 3), 'x': round(cx, 5), 'y': round(y_l, 5), 'texto': tx,
                                'size': round(size, 4), 'exacto': True})
            x += a + HUECO * cap_px
        caja = [round((0.5 * ancho_tl - total / 2) / ancho_tl, 4), round(y_l - alto_px / 2 / alto_tl, 4), round((0.5 * ancho_tl + total / 2) / ancho_tl, 4),
                round(y_l + alto_px / 2 / alto_tl, 4)]
        texto = ' '.join(textos)
        cues.append({'start': round(t0, 3), 'end': round(t1, 3), 'plantilla': 'linea', 'caja': caja, 'runs': runs + activas,
                     'lines': [{'role': 'context', 'text': texto, 'start': round(t0, 3)}]})
        plan.append({'i': n, 'tipo': 'linea', 'heroe': '', 'texto': texto, 't0': round(t0, 2), 't1': round(t1, 2)})
    return {'cues': cues, 'plan': plan}
