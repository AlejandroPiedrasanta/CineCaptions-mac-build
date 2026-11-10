# CineCaptions · By Cinema Productions
# 1_codigo/editorial_planificador.py — el Estilo 9 (v5.80): bloque editorial centrado y abajo, palo seco fino y la clave GRANDE en serif cursiva.
"""
editorial_planificador.py  (v5.80)
----------------------------------
Pedido del usuario (con un TikTok de referencia «Polish your reels»: «crea el estilo 9»; eligió la A, «el estilo 9 debe estar centrado y abajo»,
«acuérdate de la zona segura»):

  1. BLOQUES: las frases de guion_planificador partidas como el Tema 5 (tipo_planificador._trozos / _sin_colgantes: ≤ 5 palabras, ≤ 3 s).
  2. TRES LÍNEAS centradas: lo dicho ANTES de la clave en palo seco fino (Inter Regular, «v edi»), la CLAVE grande en serif cursiva (DM Serif Text
     Italic, «v edi serif») montada sobre la de arriba, y lo de DESPUÉS en palo seco con su última palabra en serif cursiva pequeña si es una
     palabra con contenido («before *posting*»). La clave: la marcada como Principal en Creativo (`mains`) o la de más puntaje (tipo_planificador._clave).
  3. TAMAÑOS de la maqueta aprobada (a 1080 de ancho): palo seco 60 px de em, la grande 172, la serif pequeña 74; lo que no cabe a lo ancho de la
     zona segura se achica. La línea de base de la GRANDE es fija (la pila no salta de un bloque a otro) y la de abajo acaba justo encima del borde
     inferior de la zona segura.
  4. CADA PALABRA entra cuando se dice (fundido de 8 fotogramas) y todas se van a la vez al acabar el bloque (run['sin_cola'], como el Estilo 8).
"""
import guion_planificador as G
import tipo_planificador as TP
import viral_captions as VC
import viral_planificador as VP
import zona_segura as ZS
from ambar_planificador import centro

CLIP, CLIP_SERIF = 'v edi', 'v edi serif'
SANS, SERIF = ('Inter 18pt', 'Regular'), ('DM Serif Text', 'Italic')       # = viral_elementos.EDI_SANS / EDI_SERIF
K_PX = {SANS: 691.0, SERIF: 627.8}           # px del em por Size a 1080 de ancho (medidos en Resolve: viral_captions.K_PX, tipo_planificador.K_PX)
CAP = {SANS: 0.737, SERIF: 0.661}
EM_S, EM_G, EM_S3 = 60.0, 172.0, 74.0        # la maqueta aprobada, a 1080 de ancho
SOBRE, BAJO_S, BAJO_G = 0.68, 0.80, 0.08     # la de arriba sube 0,68 em de la grande; la de abajo baja 0,80 em suyos + 0,08 de la grande
ABAJO_H = 0.93                               # en horizontal (sin zona segura), dónde acaba el bloque
ADELANTO, COLA, MINIMO, ANTES = 0.03, 0.45, 0.6, 0.05


def _avance(par, texto, em):
    f = VC._fuente(par, 100)
    return (f.getlength(texto) if f is not None else len(texto) * 52.0) * em / 100.0


def _serif_final(w):
    """¿La última palabra de la línea de abajo va en serif cursiva? Si dice algo (no es de las vacías ni muy corta)."""
    return w['plano'] not in G.STOP and w['plano'] not in TP.LLEVAN and len(w['plano']) >= 4


def planificar(palabras, idioma='es', ancho_tl=1080, alto_tl=1920, ancla=None, mains=None, fin_video=None, **_otros):
    """palabras [{'word','start','end'}] -> {'cues': [...], 'plan': [...]} (el contrato de viral_planificador.planificar). `ancla` no se usa: el
    bloque va siempre centrado y abajo, dentro de la zona segura."""
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
    esc = min(float(ancho_tl), alto_tl * 9.0 / 16.0) / 1080.0
    em_s, em_g, em_s3 = EM_S * esc, EM_G * esc, EM_S3 * esc
    maximo = (ZS.ancho(0.90, ancho_tl, alto_tl) - 0.04) * ancho_tl
    abajo = (ABAJO_H if horizontal else ZS.ABAJO - 0.015) * alto_tl
    y2 = abajo - 0.22 * em_s3 - BAJO_S * em_s - BAJO_G * em_g           # la base de la GRANDE, fija
    t0s = [max(0.0, pal[t[0]]['t'] - ADELANTO) for t in trozos]
    cues, plan = [], []
    for n, trozo in enumerate(trozos):
        t0 = t0s[n] if not cues else max(t0s[n], cues[-1]['end'])
        sig = t0s[n + 1] if n + 1 < len(trozos) else fin_total
        t1 = min(max(pal[trozo[-1]]['fin'] + COLA, t0 + MINIMO), max(sig, t0 + MINIMO))
        t1 = min(t1, fin_total) if fin_total > t0 + 0.2 else t1
        h = TP._clave(pal, trozo, forzados, n == 0)
        pos = trozo.index(h)
        arriba, debajo = trozo[:pos], trozo[pos + 1:]
        lineas = []                                                     # [(fila, [(k, texto, par, em)])]
        if arriba:
            lineas.append(('arriba', [(k, str(pal[k]['texto']).strip(), SANS, em_s) for k in arriba]))
        g_txt = str(pal[h]['texto']).strip()
        g_em = min(em_g, em_g * maximo / max(1.0, _avance(SERIF, g_txt, em_g)))
        lineas.append(('grande', [(h, g_txt, SERIF, g_em)]))
        if debajo:
            fila = []
            for j, k in enumerate(debajo):
                ultima = j == len(debajo) - 1
                serif = ultima and _serif_final(pal[k])
                fila.append((k, str(pal[k]['texto']).strip(), SERIF if serif else SANS, em_s3 if serif else em_s))
            lineas.append(('abajo', fila))
        bases = {'grande': y2, 'arriba': y2 - SOBRE * g_em, 'abajo': y2 + BAJO_S * em_s + BAJO_G * em_g}
        runs, lines = [], []
        for fila, items in lineas:
            esp = _avance(SANS, ' ', em_s)
            anchos = [_avance(par, t, em) for _k, t, par, em in items]
            total = sum(anchos) + esp * (len(items) - 1)
            f = min(1.0, maximo / total) if total > 0 else 1.0
            x = ancho_tl / 2.0 - total * f / 2.0
            for (k, t, par, em), a in zip(items, anchos):
                em_f, a_f = em * f, a * f
                runs.append({'k': CLIP_SERIF if par == SERIF else CLIP, 't': round(min(max(t0, pal[k]['t'] - ANTES), t1 - 0.1), 3),
                             'fin': round(t1, 3), 'x': round((x + a_f / 2.0) / ancho_tl, 5),
                             'y': round((bases[fila] - centro(par) * em_f) / alto_tl, 5), 'texto': t,
                             'size': round(em_f / (K_PX[par] * ancho_tl / 1080.0), 4), 'sin_cola': True,
                             **({'principal': True} if fila == 'grande' else {})})
                x += a_f + esp * f
            rol = {'arriba': 'context', 'grande': 'main', 'abajo': 'complement'}[fila]
            lines.append({'role': rol, 'text': ' '.join(t for _k, t, _p, _e in items), 'start': round(max(t0, pal[items[0][0]]['t']), 3)})
        top = bases['arriba'] - CAP[SANS] * em_s if arriba else bases['grande'] - 0.75 * g_em
        bottom = bases['abajo'] + 0.22 * em_s3 if debajo else bases['grande'] + 0.25 * g_em
        lines.sort(key=lambda l: l['start'])
        cues.append({'start': round(t0, 3), 'end': round(t1, 3), 'plantilla': 'editorial', 'caja': [round(top / alto_tl, 4), round(bottom / alto_tl, 4)],
                     'runs': runs, 'lines': lines, 'grande_abajo': not debajo,
                     'linea_abajo': round((CAP[SANS] * em_s if debajo else CAP[SERIF] * g_em) / alto_tl, 4)})
        plan.append({'i': n, 'tipo': 'editorial', 'heroe': g_txt, 'texto': ' '.join(l['text'] for l in lines), 't0': round(t0, 2), 't1': round(t1, 2)})
    return {'cues': cues, 'plan': plan}
