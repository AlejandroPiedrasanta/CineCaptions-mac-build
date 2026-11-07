# CineCaptions · By Cinema Productions
# 1_codigo/vista_estilos.py — v5.55 «Crea tu estilo»: la imagen quieta del caption de cada tema (Tema 1…6) sobre NEGRO, con la misma frase en los seis.
"""
vista_estilos.py
----------------
    imagenes(ajustes, ancho, alto)        -> {1..6: PIL.Image RGB de ancho×alto}
    imagen(n, ajustes, ancho, alto)       -> la del Tema n

Cada imagen = el bloque de la palabra principal de FRASE («disfrutaremos del ritmo de vibras», con «vibras» de principal) planificado con el
planificador REAL de su tema y dibujado con el render de GO sin Resolve (render_sin_resolve.preparar → render_temas.capas_de_cue; el Tema 4 con su
dibujo propio) en su instante quieto: todo ya entrado, sin animación. Se recorta a la tinta y se centra (encajado, sin deformar) en ancho×alto.
Nunca lleva emojis (se quitan del cue aunque la Edición PRO los permita). Las palabras son sintéticas: no dependen de ningún archivo del usuario.

ajustes = el de «Crea tu estilo» ({"fuente_principal": "Familia|Estilo" | "", "fuente_secundaria", "color_principal": "#RRGGBB" | "",
"color_secundario"}; vacío = lo del tema): se pintan como en el pack derivado (render_temas.ajustes_por_rol → las derivaciones de pack_personalizado).

Fondo: negro, salvo que un color elegido casi no se vea sobre negro (p. ej. #000000): entonces el gris que mejor contrasta con todos los colores
del bloque (los elegidos y el blanco de lo que se deja del tema), para que la fila nunca quede invisible.
Caché en disco por (tema, ajustes, si cada letra elegida está instalada y en qué archivo, tamaño, versión del programa, REVISION_BIN del pack, MOTOR) en ~/DaVinciSubtitles/plantillas_cache/vista_estilos
(PNG escrito con nombre temporal y renombrado: nunca queda uno a medias). Sin Qt: pensado para correr en un hilo (correr_en_hilo); un candado
serializa el dibujo porque render_temas y guion_captions guardan cachés globales.
"""
import hashlib
import json
import os
import threading
from pathlib import Path

import numpy as np
from PIL import Image

MOTOR = 'vista 2'               # súbelo si cambia cómo se dibujan las filas (la caché vieja deja de valer)
TEMAS = {1: 'Kinetic', 2: 'Referencia', 3: 'VIRAL', 4: 'Tema4', 5: 'Tema5', 6: 'Tema6'}
# La frase de muestra (palabra, inicio, fin): tiempos realistas, todo en un solo bloque en los seis temas; la principal es «vibras»
FRASE = (('disfrutaremos', 0.30, 0.95), ('del', 1.00, 1.18), ('ritmo', 1.22, 1.60), ('de', 1.64, 1.78), ('vibras', 1.85, 2.70))
PRINCIPAL = 4
# Pausa (s) tras «disfrutaremos» en cada tema: con ella el planificador de los Temas 4-6 abre un bloque nuevo en «del» y la fila enseña solo
# «del ritmo de / vibras», en minúscula (como la maqueta); sin pausa, los demás enseñan la frase entera
PAUSA = {4: 1.2, 5: 1.2, 6: 1.2}
# Cómo sale cada tema en la fila (como las imágenes de la maqueta): Tema 1 = receta «amarillo» (línea pequeña + a mano lima + héroe blanco);
# Tema 2 = «Editorial azul» (variante 5); Tema 3 = la principal con «shatter»
RECETA_T1 = 3
ESTILO_T2 = 5
EFECTO_T3 = 'v shatter'
MARGEN = (0.04, 0.08)           # lo que se deja libre alrededor (fracción del ancho y del alto)
SUPER = 2.0                     # se dibuja a ~2× el tamaño final y se reduce (bordes finos y brillos suaves)
_CANDADO = threading.Lock()
_CLAVES_EMOJI = ('emoji', 'emoji_ini', 'emoji_fin', 'emoji_linea')


# ------------------------------------------------------------------------------------------------------------------ ajustes y caché
def _normalizar(ajustes):
    try:
        import pack_personalizado as PP
        return PP.normalizar(ajustes)
    except Exception:
        a = ajustes if isinstance(ajustes, dict) else {}
        return {k: str(a.get(k) or '').strip() for k in ('fuente_principal', 'fuente_secundaria', 'color_principal', 'color_secundario')}


def carpeta_cache():
    return Path(os.path.expanduser('~')) / 'DaVinciSubtitles' / 'plantillas_cache' / 'vista_estilos'


def _version():
    try:
        import version
        return str(version.APP_VERSION)
    except Exception:
        return '?'


def _revision(pack):
    try:
        import plantillas
        return str((getattr(plantillas, 'REVISION_BIN', {}) or {}).get(pack, ''))
    except Exception:
        return ''


def _letras(norm):
    """{clave: archivo de la letra elegida o 'falta'}: si una letra que faltaba se instala (o cambia su archivo), la huella cambia y la fila se
    vuelve a dibujar (si no, la caché seguía dando la imagen con la letra del tema)."""
    out = {}
    for k in ('fuente_principal', 'fuente_secundaria'):
        partes = [p.strip() for p in str(norm.get(k) or '').split('|')]
        if not partes[0]:
            continue
        par = (partes[0], partes[1] if len(partes) > 1 and partes[1] else 'Regular')
        try:
            import render_temas as RT
            f = RT._fuente(par, 100)
            ruta = getattr(f, 'path', None) if f is not None else None
            if ruta:
                try:
                    st = os.stat(ruta)
                    ruta = f'{ruta}|{st.st_size}|{int(st.st_mtime)}'
                except Exception:
                    pass
            out[k] = str(ruta) if ruta else ('ok' if f is not None else 'falta')
        except Exception:
            out[k] = '?'
    return out


def clave(n, ajustes, ancho, alto):
    """La huella de una imagen: cambia con el tema, los ajustes, si sus letras están instaladas, el tamaño, la versión, la revisión del pack y MOTOR."""
    norm = _normalizar(ajustes)
    datos = {'tema': int(n), 'ajustes': norm, 'letras': _letras(norm), 'tam': [int(ancho), int(alto)], 'version': _version(),
             'revision': _revision(TEMAS[int(n)]), 'motor': MOTOR}
    return hashlib.sha1(json.dumps(datos, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()[:20]


def _leer_cache(ruta, ancho, alto):
    try:
        if ruta.is_file():
            with Image.open(ruta) as im:
                im = im.convert('RGB')
                if im.size == (int(ancho), int(alto)):
                    return im
    except Exception:
        pass
    return None


def _guardar_cache(ruta, im):
    """PNG con nombre temporal y renombrado (escritura atómica); si no se puede escribir, la imagen vale igual."""
    tmp = ruta.with_name(f'{ruta.stem}.{os.getpid()}.{threading.get_ident()}.tmp')
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        im.save(tmp, 'PNG', optimize=False)
        os.replace(tmp, ruta)
    except Exception:
        try:
            tmp.unlink()
        except Exception:
            pass


# ------------------------------------------------------------------------------------------------------------------ fondo
def _luminancia(rgb):
    def lin(v):
        v = v / 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(float(v)) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contraste(a, b):
    la, lb = _luminancia(a), _luminancia(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _hex(h):
    h = str(h or '').strip().lstrip('#')
    if len(h) == 3:
        h = ''.join(ch * 2 for ch in h)
    try:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) if len(h) == 6 else None
    except ValueError:
        return None


def fondo(ajustes):
    """(r, g, b) del fondo de la fila: negro mientras todos los colores elegidos contrasten con él (≥ 3:1); si no (un color oscuro), el gris que
    mejor contrasta con todos los colores del bloque (los elegidos y, por cada rol que sigue con el color del tema, blanco)."""
    norm = _normalizar(ajustes)
    colores = []
    for k in ('color_principal', 'color_secundario'):
        c = _hex(norm.get(k))
        colores.append(c if c is not None else (255, 255, 255))
    negro = (0, 0, 0)
    if min(_contraste(c, negro) for c in colores) >= 3.0:
        return negro
    grises = [(v, v, v) for v in range(0, 256, 8)]
    return max(grises, key=lambda g: (round(min(_contraste(c, g) for c in colores), 2), -g[0]))


# ------------------------------------------------------------------------------------------------------------------ el bloque de cada tema
def palabras_de_muestra(n=None):
    pausa = PAUSA.get(int(n), 0.0) if n is not None else 0.0
    return [{'word': w, 'start': a + (pausa if i else 0.0), 'end': b + (pausa if i else 0.0)} for i, (w, a, b) in enumerate(FRASE)]


def cue_de_muestra(n):
    """(estilo de dibujo, el cue de la frase de muestra en el Tema n) con el planificador real del tema; sin emojis."""
    import guion_editor
    import vista_tema as VT
    pack = TEMAS[int(n)]
    est = VT.estilo_de_pack(pack, 'v')
    if est is None:
        raise ValueError(f'Estilo {n}: sin estilo de dibujo')
    pal = palabras_de_muestra(n)
    ip = PRINCIPAL
    fin = pal[-1]['end'] + 0.6
    if est['tipo'] == 'guion':
        roles = [None] * len(pal)
        roles[ip] = guion_editor.ROL_GRANDE
        if pack == 'Referencia':
            pal[ip]['estilo'] = ESTILO_T2
        cues = guion_editor.planear(pal, roles, pack, ancla='medio', fin_video=fin, idioma='es')['cues']
    elif est['tipo'] == 'viral':
        import viral_planificador as kp
        cues = kp.planificar(pal, idioma='es', ancho_tl=1080, alto_tl=1920, ancla='bajo', mains=[ip], efectos={0: EFECTO_T3},
                             fin_video=fin)['cues']
    else:
        import kinetic_planificador as kp
        cues = kp.planificar(pal, idioma='es', ancla='bajo', mains=[ip], recetas={0: RECETA_T1}, fin_video=fin)['cues']
    if not cues:
        raise ValueError(f'Estilo {n}: el planificador no dio bloques')
    k = VT.cue_de_palabra(cues, pal[ip]['word'], pal[ip]['start'] + 0.05)
    cue = dict(cues[k if k is not None else -1])
    for c in (cue,):                       # SIN emojis, nunca
        for kk in _CLAVES_EMOJI:
            c.pop(kk, None)
    return est, cue


def _capas(est, cue, ajustes, s):
    """Las capas del cue dibujadas a escala s (diseño 1080×1920 × s) y el instante quieto."""
    import render_sin_resolve as RSR
    estilo = dict(est)
    norm = _normalizar(ajustes)
    if any(norm.values()):
        estilo['ajustes'] = norm
    W, H = max(8, int(round(1080 * s))), max(8, int(round(1920 * s)))
    capas = [c for c in RSR.preparar([cue], W, H, emoji_arriba=True, estilo=estilo) if c.get('tipo') != 'emoji']
    if not capas:
        return [], 0.0
    a, b = float(cue.get('start') or 0.0), float(cue.get('end') or 0.0)
    t = max([float(c['t0']) + float(c.get('entrada') or 0.0) for c in capas] + [a]) + 0.02
    vivas = []
    for c in capas:
        if float(c['t0']) <= t < float(c['t1']) or (float(c['t1']) >= b - 1e-6 and float(c['t0']) <= t):
            vivas.append(dict(c, entrada=0.0, t1=t + 10.0, sube=0.0))     # quieto: entero, sin fundido ni subida
    return vivas, t


def _recorte(capas, t, color_fondo=(0, 0, 0)):
    """(arr, caja): las capas ENTERAS (con todo su brillo y su sombra) compuestas sobre el fondo (uint8 HxWx3) y, dentro de arr, la caja de su
    tinta con un pequeño margen (x0, y0, x1, y1), que es lo que se encaja en la fila. Componer solo la caja cortaba la sombra ancha en seco: en un
    fondo gris se veía un rectángulo alrededor de la principal. None si no hay tinta."""
    import render_sin_resolve as RSR
    caja = RSR._tinta(capas)
    if caja is None:
        return None
    x0, y0, x1, y1 = caja
    m = int(round(0.02 * max(x1 - x0, y1 - y0))) + 2
    x0, y0, x1, y1 = x0 - m, y0 - m, x1 + m, y1 + m
    X0 = min([x0] + [int(c['x']) for c in capas])
    Y0 = min([y0] + [int(c['y']) for c in capas])
    X1 = max([x1] + [int(c['x']) + c['a'].shape[1] for c in capas])
    Y1 = max([y1] + [int(c['y']) + c['a'].shape[0] for c in capas])
    arr = np.empty((int(Y1 - Y0), int(X1 - X0), 3), np.uint8)
    arr[...] = np.asarray(color_fondo, np.uint8)
    RSR.componer(arr, [dict(c, x=c['x'] - X0, y=c['y'] - Y0) for c in capas], t)
    return arr, (x0 - X0, y0 - Y0, x1 - X0, y1 - Y0)


def _dibujar(n, ajustes, ancho, alto):
    est, cue = cue_de_muestra(n)
    bg = fondo(ajustes)
    libre_w, libre_h = ancho * (1.0 - 2 * MARGEN[0]), alto * (1.0 - 2 * MARGEN[1])
    s0 = 0.5                                                     # 1) medir la tinta a media escala
    capas, t = _capas(est, cue, ajustes, s0)
    hecho = _recorte(capas, t, bg)
    if hecho is None:
        raise ValueError(f'Estilo {n}: el bloque no tiene tinta')
    arr, (ix0, iy0, ix1, iy1) = hecho
    f0 = min(libre_w / (ix1 - ix0), libre_h / (iy1 - iy0))
    s = max(0.2, min(3.0, s0 * f0 * SUPER))                       # 2) dibujar a ~2× el tamaño final (si la medida no vale ya)
    if abs(s - s0) / s0 > 0.15:
        capas, t = _capas(est, cue, ajustes, s)
        hecho = _recorte(capas, t, bg) if capas else None
        if hecho is None:
            raise ValueError(f'Estilo {n}: el bloque no tiene tinta')
        arr, (ix0, iy0, ix1, iy1) = hecho
    im = Image.fromarray(arr, 'RGB')
    f = min(libre_w / (ix1 - ix0), libre_h / (iy1 - iy0))           # la TINTA encaja en la fila; el brillo que sobra se sale por los bordes
    tw, th = max(1, int(round(im.width * f))), max(1, int(round(im.height * f)))
    im = im.resize((tw, th), Image.LANCZOS)
    lienzo = Image.new('RGB', (int(ancho), int(alto)), bg)
    cx, cy = (ix0 + ix1) / 2.0 * f, (iy0 + iy1) / 2.0 * f            # el centro de la tinta, al centro de la fila
    lienzo.paste(im, (int(round(int(ancho) / 2.0 - cx)), int(round(int(alto) / 2.0 - cy))))
    return lienzo


# ------------------------------------------------------------------------------------------------------------------ entrada
def imagen(n, ajustes=None, ancho=480, alto=120, cache=True):
    """La imagen RGB ancho×alto del Tema n (1…6) con esos ajustes; de la caché si ya se hizo. Lanza si el tema no se puede dibujar."""
    n, ancho, alto = int(n), max(16, int(ancho)), max(16, int(alto))
    if n not in TEMAS:
        raise ValueError(f'Estilo {n}: no existe')
    ruta = carpeta_cache() / f't{n}_{clave(n, ajustes, ancho, alto)}.png'
    if cache:
        im = _leer_cache(ruta, ancho, alto)
        if im is not None:
            return im
    with _CANDADO:
        im = _dibujar(n, ajustes, ancho, alto)
    if cache:
        _guardar_cache(ruta, im)
    return im


def imagenes(ajustes=None, ancho=480, alto=120, cache=True, errores=None):
    """{1..6: PIL.Image RGB} de los seis temas. Un tema que falla sale en negro (y su error va a `errores`, una lista, si se pasa)."""
    fuera = {}
    bg = (0, 0, 0)
    try:
        bg = fondo(ajustes)
    except Exception:
        pass
    for n in TEMAS:
        try:
            fuera[n] = imagen(n, ajustes, ancho, alto, cache=cache)
        except Exception as e:
            if isinstance(errores, list):
                errores.append(f'Estilo {n}: {e}')
            fuera[n] = Image.new('RGB', (max(16, int(ancho)), max(16, int(alto))), bg)
    return fuera
