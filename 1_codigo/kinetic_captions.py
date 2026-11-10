# CineCaptions · By Cinema Productions
# 1_codigo/kinetic_captions.py — estilo «Kinetic»: la geometría de la pila de elementos (tamaños con la tipografía real, posiciones, giros, tiempos) y el .json para Resolve.
"""
kinetic_captions.py  (v5.4)
---------------------------
El estilo de los títulos de gancho de la referencia («Vertical Kinetic Hook Titles»): cada frase es una pila de elementos de distinto tipo —palabra
gigante condensada con degradado, líneas pequeñas, acentos en serif cursiva o pincel, cintas de color, anillos y subrayados— que van apareciendo a
medida que se dicen las palabras y se van todos a la vez al terminar la frase.

Este módulo NO elige qué palabra va en cada elemento (eso es kinetic_planificador.py) ni habla con Resolve: recibe las LÍNEAS de cada bloque
    {'k': clip del pack («k hero lima»), 'texto', 't', 'cap': altura de las mayúsculas (fracción del alto), 'rot', 'dx', 'solape', 'ancho': máximo (fracción del ancho)}
mide cada una con su tipografía real (Pillow), las apila centradas en un ancla vertical y devuelve los runs que lee place_kinetic_track
(CineCaptions.py / .lua):
    {'language': 'es', 'cues': [{'start', 'end', 'runs': [{'k', 'texto', 't', 'fin', 'x', 'y', 'size', 'rot', 'zx', 'zy'}]}]}
    x, y = centro del elemento (fracción del cuadro; y desde ARRIBA) · size = «Size» del Text+ · zx/zy = zoom de los trazos (anillo, subrayado).
"""
import json
import math
from pathlib import Path

import kinetic_paleta as PAL
import zona_segura as ZS

K_PX = 640.0                        # px del em por unidad de «Size» de Text+ a 1080 px de ancho (medido contra Resolve)
TINTA = 0.955                        # lo que se ve de una palabra respecto a su avance tipográfico (Pillow mide el avance)
HEROE = ('Owners Narrow', 'Black')
SERIF = ('DM Serif Text', 'Italic')
GUION = ('Antagon', 'Regular')
PLUMA = ('Yellowtail', 'Regular')    # v5.5.13 (neón): la palabra escrita a mano («k script yt …»)
ETIQUETA = ('Montserrat', 'ExtraBold')
CAP = {'Owners Narrow': 0.700, 'DM Serif Text': 0.661, 'Antagon': 0.854, 'Montserrat': 0.700, 'Yellowtail': 0.729}      # mayúsculas / em
# la tinta de las mayúsculas queda por ENCIMA del centro del Text+ (medido contra el render de Resolve): se baja el clip esta fracción del em
DY_EM = {'Owners Narrow': 0.03, 'DM Serif Text': 0.03, 'Antagon': 0.0, 'Montserrat': 0.0, 'Yellowtail': 0.04}

# lo que sabe la geometría de cada clip del pack (debe coincidir con generador_packs/kinetic_elementos.py)
def _espec(clave):
    if clave.startswith('k hero'):
        return dict(par=HEROE, mayus=True, esp=1.0, tipo='texto')
    if clave == 'k sup':
        return dict(par=HEROE, mayus=True, esp=1.04, tipo='texto')
    if clave.startswith('k serif'):
        return dict(par=SERIF, mayus=False, esp=1.0, tipo='texto')
    if clave.startswith('k script yt'):
        return dict(par=PLUMA, mayus=False, esp=1.0, tipo='texto')
    if clave.startswith('k script'):
        return dict(par=GUION, mayus=False, esp=1.0, tipo='texto')
    if clave == 'k label':
        return dict(par=ETIQUETA, mayus=True, esp=ESP_LABEL, tipo='texto')
    if clave.startswith('k ring trazo') or clave.startswith('k ring lazo'):
        return dict(tipo='trazo')
    if clave.startswith('k line trazo'):
        return dict(tipo='linea', curva=True)
    if clave.startswith('k tapes'):
        return dict(par=SERIF, mayus=True, esp=1.0, tipo='cinta', caja=(1.6, 0.4))
    if clave.startswith('k tape'):
        return dict(par=HEROE, mayus=True, esp=1.0, tipo='cinta', caja=(1.55, 0.5))
    if clave.startswith('k ring'):
        return dict(tipo='anillo')
    if clave.startswith('k line'):
        return dict(tipo='linea')
    if clave.startswith('v rojo'):                 # v5.78: el Estilo 7 (Anton): fuente_usuario._encajar mide la letra elegida contra esta
        return dict(par=('Anton', 'Regular'), mayus=False, esp=1.0, tipo='texto')
    if clave.startswith(('v ambar', 'v edi')):     # v5.80: los Estilos 8 y 9 (su letra de viral_captions.CLIPS)
        import viral_captions as VC
        return dict(par=VC.CLIPS[clave][0] if clave in VC.CLIPS else ('Montserrat', 'Regular'), mayus=False, esp=1.0, tipo='texto')
    return dict(par=HEROE, mayus=False, esp=1.0, tipo='texto')


_FUENTES = {}


def _fuente(par, px):
    clave = (par, int(round(px)))
    if clave not in _FUENTES:
        from PIL import ImageFont
        import fuentes_sistema
        ruta = fuentes_sistema.ruta_de_fuente(par[0], par[1])
        _FUENTES[clave] = ImageFont.truetype(str(ruta), max(4, int(round(px)))) if ruta else None
    return _FUENTES[clave]


def texto_visible(clave, texto):
    e = _espec(clave)
    return texto.upper() if e.get('mayus') else texto


def ancho_px(clave, texto, size, ancho_tl=1080):
    """Ancho (px) de la tinta de `texto` en el clip `clave` con ese «Size» de Text+."""
    e = _espec(clave)
    px = size * K_PX * ancho_tl / 1080.0
    t = texto_visible(clave, texto)
    f = _fuente(e['par'], px)
    avance = f.getlength(t) if f is not None else len(t) * px * 0.5
    # v5.44: el CharacterSpacing de Text+ no multiplica el avance: SUMA (esp − 1) × 1,93 em por letra (medido en Resolve 21.1.1 con las versalitas
    # del Tema 1, 12 líneas: 0,81 em por letra con 1,42). Medido como producto, «HABRÁN CONCIERTOS DE» daba 0,62 del ancho y ocupaba 0,94: se salía.
    return avance * TINTA + max(0, len(t) - 1) * (e['esp'] - 1.0) * K_ESP * px


K_ESP = 1.93                         # em que suma Text+ por letra y por unidad de CharacterSpacing por encima de 1
ESP_LABEL = 1.218                   # v5.45: el CharacterSpacing de las versalitas: 1 + 0,42/K_ESP = las .42em del kit (1,42 sumaba 0,81 em)


def size_para_cap(clave, cap_px, ancho_tl=1080):
    """El «Size» de Text+ con el que las mayúsculas miden `cap_px` px."""
    e = _espec(clave)
    return cap_px / CAP[e['par'][0]] / (K_PX * ancho_tl / 1080.0)


def cap_de_size(clave, size, ancho_tl=1080):
    e = _espec(clave)
    return size * K_PX * ancho_tl / 1080.0 * CAP[e['par'][0]]


# ------------------------------------------------------------------------------------------------------------------ la pila
AFINADO = {'ancho_max': 0.86, 'hueco': 0.20, 'hueco_min': 0.010, 'solape_cinta': 0.30, 'nominal_anillo': (0.42, 0.16), 'nominal_linea': (0.34, 0.0075),
           'grosor_linea': 0.011, 'min_size': 0.04, 'dy_texto': {'k hero': -0.0, 'k tape': 0.0}}


def _medir(linea, ancho_tl, alto_tl):
    """Completa una línea: su size, su ancho/alto visibles y el bloque que ocupa en la pila (px)."""
    clave = linea['k']
    e = _espec(clave)
    cap_px = float(linea['cap']) * alto_tl
    if e['tipo'] in ('anillo', 'linea', 'trazo'):
        linea.update(size=None, w=0.0, h=0.0, ocup=0.0)
        return linea
    size = size_para_cap(clave, cap_px, ancho_tl)
    w = ancho_px(clave, linea['texto'], size, ancho_tl)
    maximo = ZS.ancho(float(linea.get('ancho', AFINADO['ancho_max'])), ancho_tl, alto_tl) * ancho_tl      # (v5.76: dentro de la zona segura)
    caja_w = 0.0
    if e['tipo'] == 'cinta':
        alto_k, pad_k = e['caja']
        caja_w = 2.0 * cap_px * pad_k
    if w + caja_w > maximo:                       # no cabe: se reduce hasta caber
        f = (maximo - caja_w) / max(1.0, w)
        size *= max(0.2, f)
        w = ancho_px(clave, linea['texto'], size, ancho_tl)
        cap_px = cap_de_size(clave, size, ancho_tl)
    h = cap_px
    if e['tipo'] == 'cinta':
        h = cap_px * e['caja'][0]
        w += caja_w
        # girada, la cinta sube por un lado y baja por el otro: la pila le reserva ese alto para no pisar a las líneas vecinas
        import math
        h_vis = h + w * abs(math.sin(math.radians(float(linea.get('rot') or 0.0))))
        linea['h_vis'] = h_vis
    linea.update(size=max(AFINADO['min_size'], size), w=w, h=h, cap_px=cap_px)
    return linea


def _refs(trazo, textos):
    """Las líneas de texto a las que va pegado un trazo: 'sobre' = un índice o una lista de índices (dentro de `textos`, por orden de aparición)."""
    s = trazo.get('sobre', 0)
    idx = s if isinstance(s, (list, tuple)) else [s]
    refs = [textos[min(len(textos) - 1, max(0, int(i)))] for i in idx] or [textos[0]]
    return sorted({id(r): r for r in refs}.values(), key=textos.index)


def _pads_trazo(trazo, refs, ancho_tl, alto_tl):
    """(px, py) que el círculo o el lazo sobresale de sus líneas (kit: rx + 30 / ry + 14 px el círculo, + 44 / + 26 el lazo, a 1080)."""
    h = max(r.get('h_vis', r['h']) for r in refs)
    lazo = 'lazo' in str(trazo.get('k') or '')
    return (0.045 if lazo else 0.032) * ancho_tl, (0.016 if lazo else 0.012) * alto_tl + (0.18 if lazo else 0.15) * h


def apilar(lineas, ancla_y, ancho_tl=1080, alto_tl=1920):
    """lineas -> las mismas con 'x', 'y' (centro, fracción del cuadro) y la caja [arriba, abajo] de la pila (fracción del alto, desde arriba)."""
    ls = [_medir(dict(l), ancho_tl, alto_tl) for l in lineas]
    textos = [l for l in ls if _espec(l['k'])['tipo'] in ('texto', 'cinta')]
    if not textos:
        return ls, (ancla_y, ancla_y)
    # v5.5.13 (neón): un trazo a mano (círculo / lazo alrededor de una o varias líneas, subrayado debajo) pide su sitio en la pila: hueco encima de
    # la primera línea que rodea y debajo de la última (o debajo de la subrayada), para no pisar a las vecinas
    for l in ls:
        e = _espec(l['k'])
        if e['tipo'] == 'trazo':
            refs = _refs(l, textos)
            pad = _pads_trazo(l, refs, ancho_tl, alto_tl)[1] + PAL.TRAZO_GROSOR * ancho_tl
            refs[0]['_pad_arriba'] = max(refs[0].get('_pad_arriba', 0.0), pad)
            refs[-1]['_pad_abajo'] = max(refs[-1].get('_pad_abajo', 0.0), pad)
        elif e['tipo'] == 'linea' and e.get('curva'):
            ref = _refs(l, textos)[-1]
            if ref is not textos[-1]:
                ref['_pad_abajo'] = max(ref.get('_pad_abajo', 0.0), (float(l.get('sep', 0.012)) + 0.022) * alto_tl)
    if all(l.get('kit') for l in textos):
        # v5.45 (Tema 1 con Text+, «no es lo mismo»): la maqueta del kit (kit_neon.maqueta): cada línea con el ANCHO de la del kit (su fuente y su tamaño)
        # y su centro a la misma altura; la caja de la pila, la del kit. Coordenadas del kit: 1080×1920.
        for l in textos:
            m, e = l['kit'], _espec(l['k'])
            objetivo = (m['avance'] * TINTA + m['espacio']) * ancho_tl / 1080.0       # (lo que mide ancho_px: tinta + espaciado)
            w0 = ancho_px(l['k'], l['texto'], l['size'], ancho_tl)
            if w0 > 0:
                l['size'] = max(AFINADO['min_size'], l['size'] * objetivo / w0)
            l['cap_px'] = cap_de_size(l['k'], l['size'], ancho_tl)
            l['w'] = ancho_px(l['k'], l['texto'], l['size'], ancho_tl)
            l['h'] = l['cap_px'] * (e['caja'][0] if e['tipo'] == 'cinta' else 1.0)
            if e['tipo'] == 'cinta':
                l['w'] += 2.0 * l['cap_px'] * e['caja'][1]
            l['y'] = round(m['centro'] / 1920.0, 4)
            l['x'] = 0.5
        arriba = min(l['y'] * alto_tl - l['h'] / 2.0 for l in textos)
        abajo = max(l['y'] * alto_tl + l['h'] / 2.0 for l in textos)
        caja = (round(arriba / alto_tl, 4), round(abajo / alto_tl, 4))
        ls = _trazos(ls, textos, ancho_tl, alto_tl)
        return ls + _partir_grande(textos, ancho_tl), caja
    # posiciones verticales (px desde arriba, relativas al inicio de la pila)
    y = 0.0
    previo = None
    for l in textos:
        if previo is not None:
            hueco = max(AFINADO['hueco_min'] * alto_tl, AFINADO['hueco'] * min(previo['cap_px'], l['cap_px']))
            # una cinta (o un pincel) se monta sobre el héroe, pero nunca sobre una línea pequeña
            if (l.get('heroe') or previo.get('heroe')) and float((previo if l.get('heroe') else l).get('solape') or 0.0):
                otro = previo if l.get('heroe') else l
                hueco = -float(otro['solape']) * min(previo['h'], l['h'])
            y += hueco
        extra = (l.get('h_vis', l['h']) - l['h']) / 2.0
        y += extra if not (l.get('heroe') or (previo or {}).get('heroe')) else 0.0
        hueco_anillo = 0.42 * l['h'] if l.get('anillo') else 0.0          # un anillo sobresale por arriba y por abajo de su línea
        y += hueco_anillo + float(l.get('_pad_arriba', 0.0))
        l['_y0'] = y
        y += l['h'] + hueco_anillo + float(l.get('_pad_abajo', 0.0)) + (extra if not (l.get('heroe') or (previo or {}).get('heroe')) else 0.0)
        previo = l
    total = y
    arriba = ancla_y * alto_tl - total / 2.0
    arriba += ZS.meter_y(arriba / alto_tl, (arriba + total) / alto_tl, ancho_tl, alto_tl) * alto_tl      # (v5.76: la pila, dentro de la zona segura)
    for l in textos:
        centro = arriba + l['_y0'] + l['h'] / 2.0
        l['y'] = round(centro / alto_tl, 4)
        l['x'] = round(0.5 + float(l.get('dx') or 0.0), 4)
    caja = (round(arriba / alto_tl, 4), round((arriba + total) / alto_tl, 4))
    return _trazos(ls, textos, ancho_tl, alto_tl), caja


FILL_CLIP = {'acento': 'k hero lima', 'acento2': 'k hero magenta', 'blanco': 'k hero blanco'}


def _partir_grande(textos, ancho_tl):
    """v5.45 (kit: «3 JÓVENES» con la cifra en lima y cada palabra cuando se dice): la línea grande con 'partes' se queda con su PRIMERA palabra y
    devuelve una línea más por cada una de las otras, una al lado de otra con su ancho real (los trazos ya se calcularon con la línea entera)."""
    nuevas = []
    for l in textos:
        partes = (l.get('kit') or {}).get('partes')
        if not partes or (len({f for _, f, _ in partes}) < 2 and len({t for _, _, t in partes}) < 2):
            continue
        anchos = [ancho_px(l['k'], p, l['size'], ancho_tl) for p, _, _ in partes]
        hueco = ancho_px(l['k'], 'A A', l['size'], ancho_tl) - ancho_px(l['k'], 'AA', l['size'], ancho_tl)
        x = l['x'] * ancho_tl - (sum(anchos) + hueco * (len(partes) - 1)) / 2.0
        t_prev = float(l['t'])
        for k, ((p, fill, t), w) in enumerate(zip(partes, anchos)):
            d = l if k == 0 else dict(l, heroe=False, nombre='heroe_parte')
            d.update(texto=p, k=FILL_CLIP.get(fill, l['k']), x=round((x + w / 2.0) / ancho_tl, 4), w=w)
            if k and t is not None:
                d['t'] = t_prev = max(t_prev, float(t) - 0.03)          # (cada palabra cuando se dice, nunca antes que la anterior)
            if k:
                nuevas.append(d)
            x += w + hueco
    return nuevas


def _trazos(ls, textos, ancho_tl, alto_tl):
    """Los trazos se colocan respecto a su línea de referencia ('sobre': índice de la línea dentro de `textos` ordenados por aparición)."""
    for l in ls:
        e = _espec(l['k'])
        if e['tipo'] == 'trazo':                                    # v5.5.13: círculo o lazo a mano alrededor de sus líneas
            refs = _refs(l, textos)
            x0 = min(r['x'] * ancho_tl - r['w'] / 2.0 for r in refs)
            x1 = max(r['x'] * ancho_tl + r['w'] / 2.0 for r in refs)
            y0 = min(r['y'] * alto_tl - r.get('h_vis', r['h']) / 2.0 for r in refs)
            y1 = max(r['y'] * alto_tl + r.get('h_vis', r['h']) / 2.0 for r in refs)
            px, py = _pads_trazo(l, refs, ancho_tl, alto_tl)
            ancho = min(x1 - x0 + 2 * px, ZS.ancho(0.96, ancho_tl, alto_tl) * ancho_tl)
            alto = y1 - y0 + 2 * py
            nw, nh = PAL.TRAZO_NOMINAL
            l.update(x=round((x0 + x1) / 2.0 / ancho_tl, 4), y=round((y0 + y1) / 2.0 / alto_tl, 4),
                     zx=round(ancho / (nw * ancho_tl), 3), zy=round(alto / (nh * ancho_tl), 3))
            continue
        if e['tipo'] not in ('anillo', 'linea'):
            continue
        ref = _refs(l, textos)[-1]
        if e['tipo'] == 'anillo':
            nw, nh = AFINADO['nominal_anillo']
            ancho = min(ref['w'] * 1.22 + 0.04 * ancho_tl, ZS.ancho(0.9, ancho_tl, alto_tl) * ancho_tl)      # nunca más ancho que el cuadro (ni que la zona segura)
            alto = ref['h'] * 2.0
            l.update(x=ref['x'], y=ref['y'], zx=round(ancho / (nw * ancho_tl), 3), zy=round(alto / (nh * ancho_tl), 3))
        else:
            nw, nh = AFINADO['nominal_linea']
            ancho = ref['w'] * float(l.get('rel_w', 0.9))
            l.update(x=ref['x'], y=round(ref['y'] + (ref['h'] / 2.0 + float(l.get('sep', 0.012)) * alto_tl) / alto_tl, 4),
                     zx=round(ancho / (nw * ancho_tl), 3), zy=1.0)
    return ls


def _extension(l, ancho_tl, alto_tl):
    """(x0, y0, x1, y1) en px de lo que dibuja una línea de la pila ya colocada (texto o cinta con su caja; trazo, anillo o subrayado a su zoom)."""
    e = _espec(l['k'])
    x, y = float(l.get('x', 0.5)) * ancho_tl, float(l.get('y', 0.5)) * alto_tl
    if e['tipo'] in ('texto', 'cinta'):
        w, h = float(l.get('w') or 0.0), float(l.get('h_vis', l.get('h')) or 0.0)
        giro = abs(math.radians(float(l.get('rot') or 0.0)))
        if giro:                                                           # (girada, una cinta también se ensancha)
            w = w * math.cos(giro) + float(l.get('h') or 0.0) * math.sin(giro)
        w += 2.0 * ZS.AIRE_TINTA * ancho_tl if w > 0 else 0.0           # (el degradado y el contorno de la grande sobresalen de lo medido)
        if w <= 0 or h <= 0:
            return None
        return x - w / 2.0, y - h / 2.0 - 0.15 * h, x + w / 2.0, y + h / 2.0 + 0.30 * h      # (h = mayúsculas: tildes arriba, descendentes abajo)
    elif e['tipo'] in ('trazo', 'anillo', 'linea'):
        nw, nh = PAL.TRAZO_NOMINAL if e['tipo'] == 'trazo' else AFINADO['nominal_anillo'] if e['tipo'] == 'anillo' else AFINADO['nominal_linea']
        w = float(l.get('zx') or 0.0) * nw * ancho_tl + 2.0 * ZS.AIRE_TINTA * ancho_tl          # (+ el grosor del trazo)
        h = (float(l.get('zy') or 0.0) * nh * ancho_tl if e['tipo'] != 'linea' else AFINADO['grosor_linea'] * ancho_tl) + 2.0 * ZS.AIRE_TINTA * ancho_tl
    else:
        return None
    if w <= 0 or h <= 0:
        return None
    return x - w / 2.0, y - h / 2.0, x + w / 2.0, y + h / 2.0


def en_zona(ls, caja, ancho_tl=1080, alto_tl=1920):
    """v5.76 (zona segura): el bloque ENTERO (texto, cintas, anillos y trazos) cabe en la zona que deja libre la interfaz del reel
    (zona_segura): si no cabe, se achica alrededor de su centro y se corre lo justo. En horizontal no cambia nada. Devuelve (ls, caja)."""
    if not ZS.vertical(ancho_tl, alto_tl):
        return ls, caja
    ext = [x for x in (_extension(l, ancho_tl, alto_tl) for l in ls) if x]
    if not ext:
        return ls, caja
    x0, y0 = min(e[0] for e in ext) / ancho_tl, min(e[1] for e in ext) / alto_tl
    x1, y1 = max(e[2] for e in ext) / ancho_tl, max(e[3] for e in ext) / alto_tl
    y0, y1 = min(y0, float(caja[0])), max(y1, float(caja[1]))
    t = ZS.encaje(x0, y0, x1, y1, ancho_tl, alto_tl)
    if ZS.sin_cambio(t):
        return ls, caja
    s = t[0]
    for l in ls:
        if 'x' in l and 'y' in l:
            x, y = ZS.mover_punto(l['x'], l['y'], t)
            l['x'], l['y'] = round(x, 4), round(y, 4)
        for k in ('size', 'w', 'h', 'h_vis', 'cap_px'):
            if isinstance(l.get(k), (int, float)):
                l[k] = l[k] * s
        for k in ('zx', 'zy'):
            if isinstance(l.get(k), (int, float)):
                l[k] = round(l[k] * s, 3)
    a = ZS.mover_punto(0.5, caja[0], t)[1]
    b = ZS.mover_punto(0.5, caja[1], t)[1]
    return ls, (round(a, 4), round(b, 4))


def construir_cues(bloques, ancho_tl=1080, alto_tl=1920):
    """bloques: [{'t0', 't1', 'ancla', 'lineas': [...]}] -> cues con 'runs' listos para el .json. Una línea: ver el docstring del módulo."""
    cues = []
    for b in bloques:
        ls, caja = apilar(b['lineas'], b.get('ancla', 0.6), ancho_tl, alto_tl)
        ls, caja = en_zona(ls, caja, ancho_tl, alto_tl)
        runs = []
        for l in ls:
            e = _espec(l['k'])
            r = {'k': l['k'], 't': round(float(l.get('t', b['t0'])), 3), 'x': l['x'], 'y': l['y']}
            if e['tipo'] in ('texto', 'cinta'):
                r['texto'] = texto_visible(l['k'], l['texto'])
                r['size'] = round(l['size'], 4)
                r['y'] = round(l['y'] + DY_EM.get(e['par'][0], 0.0) * l['size'] * K_PX * ancho_tl / 1080.0 / alto_tl, 4)
            else:
                r['zx'], r['zy'] = l['zx'], l['zy']
            if l.get('rot'):
                r['rot'] = round(float(l['rot']), 2)
            runs.append(r)
        runs.sort(key=lambda r: r['t'])
        cues.append({'start': round(b['t0'], 3), 'end': round(b['t1'], 3), 'plantilla': b.get('receta'), 'caja': list(caja), 'runs': runs})
    return cues


def variantes_trazo(cues):
    """v5.45 (el usuario: «el dibujo de rings no lo hace bien»): el círculo y el lazo a mano van con la variante del pack que ya tiene su forma
    («k ring trazo lima 36»: alto/ancho 0,36) y un zoom IGUAL en x e y; con ZoomX ≠ ZoomY el trazo salía deformado. Solo para Resolve (el .json de la
    pista); la vista y GO sin Resolve siguen con zx/zy sobre TRAZO_NOMINAL. Cambia los cues en su sitio."""
    nw, nh = PAL.TRAZO_NOMINAL
    for cue in cues or []:
        for r in cue.get('runs') or []:
            k = str(r.get('k') or '')
            if k.startswith('k line trazo') and len(k.split()) == 4:        # v5.47: el subrayado igual: su variante de ancho y zoom igual en x e y
                ancho = float(r.get('zx') or 1.0) * AFINADO['nominal_linea'][0]
                v = min(PAL.SUBRAYADO_ANCHOS, key=lambda a: abs(a - ancho))
                z = round(ancho / v, 3)
                r.update(k=f'{k} {int(round(v * 100))}', zx=z, zy=z)
                continue
            if not (k.startswith('k ring trazo') or k.startswith('k ring lazo')) or len(k.split()) > 4:
                continue
            zx, zy = float(r.get('zx') or 1.0), float(r.get('zy') or 1.0)
            ancho, alto = zx * nw, zy * nh
            a = min(PAL.ASPECTOS_TRAZO, key=lambda v: abs(v - alto / max(ancho, 1e-6)))
            z = round(ancho / PAL.TRAZO_VARIANTE_ANCHO, 3)
            r.update(k=f'{k} {int(round(a * 100))}', zx=z, zy=z)
    return cues


def escribir(cues, ruta, idioma='es'):
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    datos = {'language': idioma, 'cues': cues}
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding='utf-8')
    try:                                         # v5.4.16: Resolve Free 21.1 no deja a los scripts leer archivos (sin io): lee este mismo dato por su gemelo «<archivo>.lua»
        import sidecar_lua
        sidecar_lua.escribir_sidecar(ruta, datos)
    except Exception:
        pass
    return str(ruta)
