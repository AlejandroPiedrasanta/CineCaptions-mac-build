# CineCaptions · By Cinema Productions
# 1_codigo/guion_captions.py — estilo «guion»: la frase se arma palabra a palabra (cada palabra, su pista, su estilo, su sitio y su momento).
"""
guion_captions.py  (v5.9)
-------------------------
El estilo de los captions virales de la referencia (REFERENCIA.mp4): cada frase es una pila de líneas pequeñas (fina, con alguna palabra en
negrita) y una palabra GRANDE con un estilo propio (degradado, serif cursiva, pastilla dorada, tachado, subrayado…). Las palabras van apareciendo
a medida que se dicen y la pila entera se va a la vez cuando acaba la frase.

Este módulo no habla con Resolve: arma los datos que lee place_guion_track (CineCaptions.py / .lua):

    {'language': 'es', 'cues': [{'start', 'end', 'estilo', 'runs': [{'rol', 'texto', 't', 'fin', 'x', 'y', 'estilo'}]}]}

    rol 'main' -> palabra grande ("principal n"), 'context' -> palabra fina ("arriba"), 'complement' -> palabra en negrita ("abajo").
    x, y = centro de la palabra en fracción del cuadro (y desde ARRIBA).

Una LÍNEA pequeña son varias palabras de dos pesos seguidas: aquí se miden con la tipografía de verdad (Pillow) para que cada tramo caiga justo
a continuación del anterior y la línea entera quede centrada donde se pide.
"""
import json
from pathlib import Path

FINA = ('Poppins', 'Light')
NEGRITA = ('Poppins', 'Bold')
# píxeles de letra por unidad de «Size» del macro a 1080 px de ancho (se calibra contra el render de Resolve; ver AFINADO)
K_PX = 640.0
TAM_PEQUENA = 0.118          # el «Size» de arriba/abajo del pack Referencia (~75 px a 1080 de ancho)
# Afinado contra el render de Resolve (v5.9): Pillow mide el AVANCE de las letras y lo que se ve (la tinta) es un poco menos; los presets de Amro
# llevan su tipografía DENTRO del comp, así que su ancho se mide una vez en Resolve: tinta en px a zoom 1 = k × (ancho de Inter Black a 100 px) / 100.
AFINADO = {'ancho': 1.0, 'espacio': 0.55, 'tinta_pequena': 0.975, 'tinta_principal': 0.95, 'amro_k': {3: None, 6: 1.99, 7: 0.964, 8: 1.53},
           'dy': {1: -0.021},      # la tinta de las mayúsculas queda más abajo que el centro de la caja: se sube
           # los presets de Amro se revelan letra a letra (~0,3 s); la referencia los muestra enteros al instante: el comp arranca ya adelantado (s)
           'salto_amro': {3: 0.2, 6: 0.2, 7: 0.2, 8: 0.14}}

_FUENTES = {}


def _fuente(par, px):
    clave = (par, int(round(px)))
    if clave not in _FUENTES:
        from PIL import ImageFont
        import fuentes_sistema
        ruta = fuentes_sistema.ruta_de_fuente(par[0], par[1])
        _FUENTES[clave] = ImageFont.truetype(str(ruta), int(round(px))) if ruta else None
    return _FUENTES[clave]


def ancho_px(texto, par=FINA, tam=TAM_PEQUENA, ancho_tl=1080):
    """Ancho (px del cuadro) de `texto` con esa tipografía y ese Size."""
    f = _fuente(par, tam * K_PX * ancho_tl / 1080.0)
    if f is None:
        return len(texto) * tam * K_PX * 0.55 * ancho_tl / 1080.0
    return f.getlength(texto) * AFINADO['ancho']


def datos_variantes(pack='Referencia', formato='v'):
    """{n: {'fuente': (familia, estilo), 'tam': Size, 'mayus': bool, 'amro': bool}} del principal de cada variante del pack (de su .variantes.json)."""
    clave = (pack, formato)
    if clave in _VARIANTES:
        return _VARIANTES[clave]
    salida = {}
    try:
        import plantillas
        p = plantillas.buscar_pack(pack)
        drb = Path(p.ruta_drb(formato))
        crudo = json.loads(drb.with_name(drb.stem + '.variantes.json').read_text(encoding='utf-8'))
        for n, v in crudo.items():
            m = (v.get('roles') or {}).get('main') or {}
            salida[int(n)] = {'fuente': tuple(m.get('f1') or ('Poppins', 'Bold')), 'tam': float(m.get('tam') or 0.2), 'mayus': bool(m.get('mayus')),
                              'amro': bool(v.get('amro')), 'color': str(m.get('color') or v.get('color') or '#FFFFFF'), 'nombre': str(v.get('nombre') or '')}
    except Exception:
        pass
    _VARIANTES[clave] = salida
    return salida


_VARIANTES = {}


def ancho_main(texto, n, pack='Referencia', ancho_tl=1080):
    """Ancho (px) de la palabra grande con el estilo n SIN zoom, o None si no se puede medir (los presets de Amro llevan su tipografía dentro)."""
    d = datos_variantes(pack).get(int(n or 0))
    if not d:
        return None
    if d['amro']:
        k = AFINADO['amro_k'].get(int(n))
        f = _fuente(('Inter', 'Black'), 100)
        if not k or f is None:
            return None
        return k * f.getlength(texto) * ancho_tl / 1080.0
    f = _fuente(d['fuente'], d['tam'] * K_PX * ancho_tl / 1080.0)
    if f is None:
        return None
    return f.getlength(texto.upper() if d['mayus'] else texto) * AFINADO['ancho'] * AFINADO['tinta_principal']


def distribuir(tramos, cx, ancho_tl=1080, tam=TAM_PEQUENA, w=None):
    """tramos [(texto, 'L'|'B')] -> ([x centro de cada tramo], escala): la línea entera centrada en `cx` (fracción del ancho) y, si se pide un ancho
    total `w` (fracción del ancho), reducida o ampliada hasta ocuparlo (escala = zoom de cada tramo)."""
    anchos = [ancho_px(t, FINA if p == 'L' else NEGRITA, tam, ancho_tl) for t, p in tramos]
    espacio = ancho_px(' ', FINA, tam, ancho_tl) * AFINADO['espacio']      # entre tramos va un espacio más corto: los clips ya llevan su propio margen
    total = sum(anchos) + espacio * (len(tramos) - 1)
    escala = (w * ancho_tl / (total * AFINADO['tinta_pequena'])) if (w and total) else 1.0
    escala = max(0.4, min(2.0, escala))
    x = cx * ancho_tl - total * escala / 2.0
    salida = []
    for a in anchos:
        salida.append((x + a * escala / 2.0) / ancho_tl)
        x += (a + espacio) * escala
    return salida, escala


def construir_cues(bloques, pack='Referencia', ancho_tl=1080, tam=TAM_PEQUENA):
    """bloques: [{'t0', 't1', 'estilo', 'lineas': [...]}]. Una línea:
         ('M', [(texto, t[, estilo])], cx, y, w[, zoom])    la palabra grande: w = ancho que ocupa (fracción del ancho; se ajusta con el zoom), o zoom fijo
         ('S', [(texto, 'L'|'B', t)], cx, y, w)             una línea pequeña: tramos en su orden, centrada en cx y de ancho total w
       Devuelve la lista de bloques con 'runs' lista para el JSON."""
    cues = []
    for b in bloques:
        runs = []
        for linea in b['lineas']:
            tipo, partes, cx, y = linea[:4]
            w = linea[4] if len(linea) > 4 else None
            if tipo == 'M':
                z_fijo = linea[5] if len(linea) > 5 else None
                for parte in partes:
                    texto, t = parte[0], parte[1]
                    n = (parte[2] if len(parte) > 2 and parte[2] else None) or b.get('estilo')
                    d = datos_variantes(pack).get(int(n or 0)) or {}
                    r = {'rol': 'main', 'texto': texto.upper() if (d.get('mayus') and not d.get('amro')) else texto, 't': t, 'x': cx,
                         'y': round(y + AFINADO['dy'].get(int(n or 0), 0.0), 4)}
                    if len(parte) > 2 and parte[2]:
                        r['estilo'] = parte[2]
                    z = z_fijo
                    a = ancho_main(texto, n, pack, ancho_tl)
                    if a and not d.get('amro'):
                        r['ancho_rel'] = round(a / float(ancho_tl), 3)      # v5.5: lo que mide la palabra (fracción del ancho del comp, SIN zoom): el script ajusta el recorrido del barrido de luz a eso
                    if z is None and w:
                        if a:
                            z = max(0.3, min(2.5, w * ancho_tl / a))
                    if z and abs(z - 1.0) > 0.005:
                        r['zoom'] = round(z, 3)
                    if d.get('amro') and AFINADO['salto_amro'].get(int(n or 0)):
                        r['salto'] = AFINADO['salto_amro'][int(n)]
                    runs.append(r)
            else:
                xs, escala = distribuir([(p[0], p[1]) for p in partes], cx, ancho_tl, tam, w)
                for (texto, peso, t), x in zip(partes, xs):
                    r = {'rol': 'context' if peso == 'L' else 'complement', 'texto': texto, 't': t, 'x': round(x, 4), 'y': y}
                    if abs(escala - 1.0) > 0.005:
                        r['zoom'] = round(escala, 3)
                    runs.append(r)
        cue = {'start': b['t0'], 'end': b['t1'], 'estilo': b.get('estilo'), 'runs': runs}
        if b.get('caja'):
            cue['caja'] = list(b['caja'])
        cues.append(cue)
    return cues


def escribir(cues, ruta, idioma='es'):
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps({'language': idioma, 'cues': cues}, ensure_ascii=False, indent=1), encoding='utf-8')
    return str(ruta)
