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
from pathlib import Path

import kinetic_paleta as PAL

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
        return dict(par=ETIQUETA, mayus=True, esp=1.42, tipo='texto')
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
    return avance * e['esp'] * TINTA


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
    maximo = float(linea.get('ancho', AFINADO['ancho_max'])) * ancho_tl
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
    for l in textos:
        centro = arriba + l['_y0'] + l['h'] / 2.0
        l['y'] = round(centro / alto_tl, 4)
        l['x'] = round(0.5 + float(l.get('dx') or 0.0), 4)
    caja = (round(arriba / alto_tl, 4), round((arriba + total) / alto_tl, 4))
    # los trazos se colocan respecto a su línea de referencia ('sobre': índice de la línea dentro de `textos` ordenados por aparición)
    for l in ls:
        e = _espec(l['k'])
        if e['tipo'] == 'trazo':                                    # v5.5.13: círculo o lazo a mano alrededor de sus líneas
            refs = _refs(l, textos)
            x0 = min(r['x'] * ancho_tl - r['w'] / 2.0 for r in refs)
            x1 = max(r['x'] * ancho_tl + r['w'] / 2.0 for r in refs)
            y0 = min(r['y'] * alto_tl - r.get('h_vis', r['h']) / 2.0 for r in refs)
            y1 = max(r['y'] * alto_tl + r.get('h_vis', r['h']) / 2.0 for r in refs)
            px, py = _pads_trazo(l, refs, ancho_tl, alto_tl)
            ancho = min(x1 - x0 + 2 * px, 0.96 * ancho_tl)
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
            ancho = min(ref['w'] * 1.22 + 0.04 * ancho_tl, 0.9 * ancho_tl)             # nunca más ancho que el cuadro
            alto = ref['h'] * 2.0
            l.update(x=ref['x'], y=ref['y'], zx=round(ancho / (nw * ancho_tl), 3), zy=round(alto / (nh * ancho_tl), 3))
        else:
            nw, nh = AFINADO['nominal_linea']
            ancho = ref['w'] * float(l.get('rel_w', 0.9))
            l.update(x=ref['x'], y=round(ref['y'] + (ref['h'] / 2.0 + float(l.get('sep', 0.012)) * alto_tl) / alto_tl, 4),
                     zx=round(ancho / (nw * ancho_tl), 3), zy=1.0)
    return ls, caja


def construir_cues(bloques, ancho_tl=1080, alto_tl=1920):
    """bloques: [{'t0', 't1', 'ancla', 'lineas': [...]}] -> cues con 'runs' listos para el .json. Una línea: ver el docstring del módulo."""
    cues = []
    for b in bloques:
        ls, caja = apilar(b['lineas'], b.get('ancla', 0.6), ancho_tl, alto_tl)
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
