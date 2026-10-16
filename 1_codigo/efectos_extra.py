# CineCaptions · By Cinema Productions
# 1_codigo/efectos_extra.py — más efectos para la página «Efectos» (v5.4.8): números 1-2-3, pegatinas, subrayados, overlays continuos, efectos propios y cierre (outro).
"""
efectos_extra.py
----------------
Todo lo de aquí son CLIPS que se colocan encima del video en pistas «FX-…» (como la intro, las transiciones de luz y los iconos; V1/A1 y los captions no se tocan):

  * NÚMEROS     una insignia con «1», «2», «3» que sale cuando el que habla enumera («primero, segundo…», «paso 1», «number two»…). Secuencia de PNG con transparencia.
  * PEGATINAS   emojis grandes con borde blanco (estilo sticker) que saltan en una esquina cuando se dice la palabra que tú asignas (dinero → 💰). Mismas imágenes
                que los emojis de los captions (2_recursos/emojis).
  * ÉNFASIS     un subrayado o un círculo dibujado a mano que se traza solo sobre la frase importante (altura elegible: arriba / centro / abajo).
  * OVERLAYS    polvo, grano de película o luz suave en bucle durante TODO el video (mezclados en «Screen» y con poca fuerza).
  * PROPIOS     tus archivos (MOV/MP4 con o sin alpha, PNG, GIF, WebP animado, APNG): en la intro, en los cortes, en bucle o en las palabras que elijas, con el modo
                de mezcla que quieras (Screen, Multiply o Normal).
  * OUTRO       un cierre: «Sígueme para más» animado, tu logo o una pantalla final, con su sonido.

Todo se anima aquí (Pillow + PyAV, sin ffmpeg) y se guarda en la caché de efectos (~/DaVinciSubtitles/efectos_cache; la limpia efectos_visuales.limpiar_cache).
`planificar_extra()` decide qué va y cuándo; `preparar()` lo convierte en un archivo o secuencia para el timeline concreto.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import re
import shutil
import unicodedata
from pathlib import Path

import efectos_visuales as F

FPS = F.FPS_FX
VERDE = (25, 210, 122)
BLANCO = (255, 255, 255)

# ----------------------------------------------------------------------------------------------------------------------- catálogo
OVERLAYS = (('polvo', 'Polvo', 'Partículas de polvo que flotan y brillan un poco, todo el video.'),
            ('grano', 'Grano de película', 'Un grano fino de cine encima de toda la imagen.'),
            ('luz', 'Luz suave', 'Un resplandor cálido que se mueve despacio.'))
DUR_OVERLAY_S = 4.0
ENFASIS = (('subrayado', 'Subrayado'), ('circulo', 'Círculo'))
ALTURAS = {'arriba': 0.30, 'centro': 0.52, 'abajo': 0.70}
OUTROS = (('cta', 'Sígueme', 'Un botón animado «Sígueme para más» en los últimos segundos.'),
          ('logo', 'Tu logo', 'Tu logo que entra con un destello al final.'),
          ('final', 'Pantalla final', 'El video se oscurece y sale tu logo con la invitación a seguirte.'))
USO_PROPIOS = (('intro', 'Intro'), ('cortes', 'Cortes'), ('continuo', 'Todo el video'), ('palabras', 'Palabras'))
MODOS_PROPIOS = (('screen', 'Screen'), ('multiply', 'Multiply'), ('normal', 'Normal'))
DUR_NUMERO_S = 2.1
DUR_PEGATINA_S = 2.4
DUR_ENFASIS_S = 1.9
DUR_OUTRO_S = {'cta': 3.4, 'logo': 3.0, 'final': 3.6}
EXT_IMAGEN = {'.png', '.gif', '.webp', '.apng', '.jpg', '.jpeg'}
EXT_VIDEO = {'.mov', '.mp4', '.m4v', '.webm', '.mkv', '.avi'}

# las palabras de fábrica de las pegatinas (id de emoji de 2_recursos/emojis): es / en; el usuario las cambia en la página
PEGATINAS_POR_DEFECTO = {
    'dinero': 'money_bag', 'money': 'money_bag', 'plata': 'money_bag', 'cash': 'money_with_wings', 'ganar': 'money_with_wings', 'earn': 'money_with_wings',
    'casa': 'house', 'house': 'house', 'home': 'house', 'hogar': 'house', 'fuego': 'fire', 'fire': 'fire', 'caliente': 'fire', 'hot': 'fire',
    'amor': 'red_heart', 'love': 'red_heart', 'corazón': 'red_heart', 'corazon': 'red_heart', 'idea': 'light_bulb', 'ideas': 'light_bulb',
    'cohete': 'rocket', 'rocket': 'rocket', 'rápido': 'rocket', 'rapido': 'rocket', 'fast': 'rocket', 'trofeo': 'trophy', 'trophy': 'trophy', 'ganador': 'trophy', 'winner': 'trophy',
    'cuidado': 'warning', 'warning': 'warning', 'ojo': 'eyes', 'mira': 'eyes', 'look': 'eyes', 'watch': 'eyes', 'secreto': 'shushing_face', 'secret': 'shushing_face',
    'cerebro': 'brain', 'brain': 'brain', 'piensa': 'thinking_face', 'think': 'thinking_face', 'tiempo': 'hourglass_not_done', 'time': 'hourglass_not_done',
    'video': 'movie_camera', 'cámara': 'camera', 'camara': 'camera', 'camera': 'camera', 'música': 'musical_notes', 'musica': 'musical_notes', 'music': 'musical_notes',
    'estrella': 'star', 'star': 'star', 'nuevo': 'sparkles', 'new': 'sparkles', 'magia': 'sparkles', 'magic': 'sparkles', 'fuerza': 'flexed_biceps', 'strong': 'flexed_biceps',
    'gratis': 'free_button', 'free': 'free_button', 'llave': 'key', 'key': 'key', 'clave': 'key', 'diamante': 'gem_stone', 'diamond': 'gem_stone', 'lujo': 'gem_stone', 'luxury': 'gem_stone',
    'felicidades': 'party_popper', 'congrats': 'party_popper', 'fiesta': 'party_popper', 'party': 'party_popper', 'risa': 'face_with_tears_of_joy', 'funny': 'face_with_tears_of_joy',
    'wow': 'exploding_head', 'increíble': 'exploding_head', 'increible': 'exploding_head', 'amazing': 'exploding_head', 'perfecto': 'ok_hand', 'perfect': 'ok_hand',
    'rey': 'crown', 'king': 'crown', 'reina': 'crown', 'queen': 'crown', 'corona': 'crown', 'meta': 'bullseye', 'goal': 'bullseye', 'objetivo': 'bullseye',
}

_ORDINALES = {
    1: ('primero', 'primer', 'primera', 'first', 'primeiro', 'primeira', 'premier', 'première', 'uno', 'one', 'um', 'une'),
    2: ('segundo', 'segunda', 'second', 'deuxième', 'dos', 'two', 'dois', 'deux'),
    3: ('tercero', 'tercer', 'tercera', 'third', 'terceiro', 'terceira', 'troisième', 'tres', 'three', 'três', 'trois'),
    4: ('cuarto', 'cuarta', 'fourth', 'quarto', 'quarta', 'quatrième', 'cuatro', 'four', 'quatro', 'quatre'),
    5: ('quinto', 'quinta', 'fifth', 'cinquième', 'cinco', 'five', 'cinq'),
    6: ('sexto', 'sexta', 'sixth', 'sixième', 'seis', 'six', 'seis'),
    7: ('séptimo', 'septimo', 'séptima', 'septima', 'seventh', 'sétimo', 'siete', 'seven', 'sete', 'sept'),
    8: ('octavo', 'octava', 'eighth', 'oitavo', 'ocho', 'eight', 'oito', 'huit'),
    9: ('noveno', 'novena', 'ninth', 'nono', 'nueve', 'nine', 'nove', 'neuf'),
}
_SOLO_ORDINAL = {1: {'primero', 'primer', 'primera', 'first', 'primeiro', 'primeira', 'premier', 'première'}, 2: {'segundo', 'segunda', 'second', 'deuxième'},
                 3: {'tercero', 'tercer', 'tercera', 'third', 'terceiro', 'terceira', 'troisième'}, 4: {'cuarto', 'cuarta', 'fourth', 'quarto', 'quarta', 'quatrième'},
                 5: {'quinto', 'quinta', 'fifth', 'cinquième'}, 6: {'sexto', 'sexta', 'sixth', 'sixième'}, 7: {'séptimo', 'septimo', 'séptima', 'septima', 'seventh', 'sétimo'},
                 8: {'octavo', 'octava', 'eighth', 'oitavo'}, 9: {'noveno', 'novena', 'ninth', 'nono'}}
_DISPARADORES = ('paso', 'pasos', 'step', 'tip', 'consejo', 'razón', 'razon', 'reason', 'number', 'número', 'numero', 'etapa', 'regla', 'rule', 'punto', 'point', 'secreto', 'secret',
                 'hack', 'truco', 'idea', 'error', 'mistake', 'lección', 'leccion', 'lesson', 'motivo', 'passo', 'dica', 'razão', 'étape', 'astuce', 'raison')


def _plegar(t):
    t = unicodedata.normalize('NFKD', str(t or '').lower())
    return ''.join(c for c in t if not unicodedata.combining(c)).strip(" .,;:!?¡¿\"'()[]«»…")


# ----------------------------------------------------------------------------------------------------------------------- piezas de dibujo
def _fuente(tam):
    from PIL import ImageFont
    base = F.carpeta_efectos().parent / 'fonts'
    for nombre in ('Inter-Black.ttf', 'Inter_18pt-Black.ttf', 'Gotham-Ultra.otf', 'HelveticaNeueBlack.otf'):
        r = base / nombre
        if r.is_file():
            try:
                return ImageFont.truetype(str(r), int(tam))
            except Exception:
                pass
    return ImageFont.load_default()


def _huella(*partes):
    """Una huella corta y ESTABLE (hash() de Python cambia en cada ejecución) de lo que define un archivo de la caché."""
    return hashlib.md5('|'.join(str(p) for p in partes).encode('utf-8')).hexdigest()[:10]


def _carpeta_cache(nombre):
    return F.CACHE / f'{nombre}_{F.REVISION}'


def _secuencia(nombre, n, dibujar):
    """Genera (o reutiliza) una secuencia de PNG RGBA: dibujar(f, n) -> imagen RGBA del tamaño del lienzo. Devuelve {'patron', 'n', 'dur'} o None."""
    carpeta = _carpeta_cache(nombre)
    patron = carpeta / 'f_%04d.png'
    listo = {'patron': str(patron), 'n': n, 'dur': n / float(FPS)}
    if F._secuencia_lista(carpeta, n):
        return listo
    with F._LOCK_SECUENCIAS:
        if F._secuencia_lista(carpeta, n):
            return listo
        tmp = carpeta.with_name(carpeta.name + '_tmp')
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True, exist_ok=True)
        try:
            for f in range(n):
                dibujar(f, n).save(tmp / f'f_{f + 1:04d}.png', compress_level=3)
        except Exception:
            shutil.rmtree(tmp, ignore_errors=True)
            return None
        shutil.rmtree(carpeta, ignore_errors=True)
        tmp.rename(carpeta)
        F.limpiar_cache()
    return listo


def _poner(lienzo, im, cx, cy):
    """Pega `im` (RGBA) centrada en (cx, cy) recortando lo que se salga."""
    W, H = lienzo.size
    x, y = int(round(cx - im.width / 2.0)), int(round(cy - im.height / 2.0))
    ix0, iy0 = max(0, -x), max(0, -y)
    ix1, iy1 = min(im.width, W - x), min(im.height, H - y)
    if ix1 > ix0 and iy1 > iy0:
        lienzo.alpha_composite(im, (x + ix0, y + iy0), (ix0, iy0, ix1, iy1))


def _con_sombra(im, desenfoque=10, desp=(0, 8), opacidad=0.45):
    """La imagen con una sombra suave debajo (para que el sticker «flote»)."""
    from PIL import Image, ImageFilter
    pad = int(desenfoque * 3) + max(abs(desp[0]), abs(desp[1])) + 2
    base = Image.new('RGBA', (im.width + pad * 2, im.height + pad * 2), (0, 0, 0, 0))
    sombra = Image.new('RGBA', base.size, (0, 0, 0, 0))
    sombra.paste((0, 0, 0, int(255 * opacidad)), (pad + desp[0], pad + desp[1]), im.split()[3])
    sombra = sombra.filter(ImageFilter.GaussianBlur(desenfoque))
    base.alpha_composite(sombra)
    base.alpha_composite(im, (pad, pad))
    return base


def _anim_pop(t, dur, entrada=0.38, salida=0.30):
    """(escala, opacidad, u_entrada) de una pieza que entra con rebote, se mantiene y sale."""
    if t < entrada:
        u = max(0.0, t / entrada)
        return max(0.01, F._rebote(u)), min(1.0, u * 4.0), u
    if t > dur - salida:
        v = F._suave((t - (dur - salida)) / salida)
        return max(0.05, 1.0 - 0.28 * v), 1.0 - v, 1.0
    return 1.0, 1.0, 1.0


def _giro_y_flote(t, fase, u):
    return (1.0 - F._suave(u)) * (-14.0 if fase % 2 == 0 else 14.0) + 2.0 * math.sin(2 * math.pi * (t / 2.6 + fase * 0.3)), 6.0 * math.sin(2 * math.pi * (t / 2.2 + fase * 0.2))


# ----------------------------------------------------------------------------------------------------------------------- números 1-2-3
def detectar_numeros(palabras):
    """[{'n': 1, 'ini': s}] cuando el que habla enumera: «primero… segundo…», «paso 1», «number two»… Solo cuenta una SECUENCIA (1, 2, 3…): un «second» suelto es un segundo
    de tiempo, no el número 2."""
    toks = [(_plegar(F._texto_palabra(p)), float(p.get('start', 0.0))) for p in palabras or []]
    candidatos = []
    for i, (w, t) in enumerate(toks):
        if not w:
            continue
        previo = toks[i - 1][0] if i else ''
        for n, formas in _ORDINALES.items():
            plan = {_plegar(x) for x in formas}
            es_ordinal = w in {_plegar(x) for x in _SOLO_ORDINAL.get(n, ())}
            es_numero = w in plan or w == str(n)
            if es_ordinal or (es_numero and previo in {_plegar(d) for d in _DISPARADORES}):
                candidatos.append({'n': n, 'ini': t, 'w': w})
                break
    # una secuencia creciente que empiece en 1 (o 2, si el 1 se dijo antes de la palabra clave), sin repetir números
    mejor, esperado = [], 1
    for c in candidatos:
        if c['n'] == esperado:
            mejor.append(c)
            esperado += 1
        elif c['n'] == 1 and not mejor:
            mejor, esperado = [c], 2
    if len(mejor) < 2:
        return []
    return [{'n': c['n'], 'ini': round(c['ini'], 3)} for c in mejor]


def _badge_numero(txt, d, ss=3):
    """La insignia (círculo verde con borde blanco y el número) a d×d píxeles."""
    from PIL import Image, ImageDraw
    D = d * ss
    im = Image.new('RGBA', (D, D), (0, 0, 0, 0))
    g = ImageDraw.Draw(im)
    borde = int(D * 0.055)
    g.ellipse((0, 0, D - 1, D - 1), fill=BLANCO + (255,))
    g.ellipse((borde, borde, D - 1 - borde, D - 1 - borde), fill=VERDE + (255,))
    brillo = Image.new('RGBA', (D, D), (0, 0, 0, 0))
    ImageDraw.Draw(brillo).ellipse((borde * 1.6, borde * 1.4, D * 0.78, D * 0.52), fill=(255, 255, 255, 46))
    im.alpha_composite(brillo)
    tam = int(D * (0.62 if len(txt) == 1 else 0.46))
    fuente = _fuente(tam)
    caja = g.textbbox((0, 0), txt, font=fuente)
    x, y = (D - (caja[2] - caja[0])) / 2 - caja[0], (D - (caja[3] - caja[1])) / 2 - caja[1] - D * 0.015
    g.text((x + D * 0.012, y + D * 0.02), txt, font=fuente, fill=(6, 70, 40, 255))
    g.text((x, y), txt, font=fuente, fill=BLANCO + (255,))
    return im.resize((d, d), Image.Resampling.LANCZOS)


def _posicion_libre(ancho, alto, evitar, k=0):
    """Una esquina superior que no pise las zonas a evitar (fracciones x0, y0, x1, y1). k alterna el lado."""
    vertical = alto >= ancho
    huecos = ([(0.17, 0.17), (0.83, 0.17), (0.17, 0.29), (0.83, 0.29), (0.5, 0.11)] if vertical else [(0.10, 0.18), (0.90, 0.18), (0.10, 0.34), (0.90, 0.34)])
    if k % 2:
        huecos = huecos[1::2] + huecos[0::2]
    r = 0.13 if vertical else 0.09
    for cx, cy in huecos:
        caja = (cx - r, cy - r * (ancho / alto if vertical else 1.5), cx + r, cy + r * (ancho / alto if vertical else 1.5))
        if not any(not (caja[2] < z[0] or caja[0] > z[2] or caja[3] < z[1] or caja[1] > z[3]) for z in (evitar or [])):
            return cx, cy
    return huecos[0]


def secuencia_numero(n, ancho, alto, evitar=None, k=0):
    """Insignia con el número n (2,1 s). Devuelve {'patron', 'n', 'dur'}."""
    from PIL import Image
    txt = str(int(n))
    cx0, cy0 = _posicion_libre(ancho, alto, evitar, k)
    d = int(min(ancho, alto) * 0.205)
    badge = _con_sombra(_badge_numero(txt, d), desenfoque=max(6, d // 14), desp=(0, d // 22))
    total = int(round(DUR_NUMERO_S * FPS))
    clave = f'numero_{txt}_{ancho}x{alto}_{int(cx0 * 100)}-{int(cy0 * 100)}'

    def dibujar(f, n_):
        t = f / float(FPS)
        esc, op, u = _anim_pop(t, DUR_NUMERO_S)
        giro, dy = _giro_y_flote(t, int(n), u)
        lienzo = Image.new('RGBA', (ancho, alto), (0, 0, 0, 0))
        if op <= 0.004:
            return lienzo
        im = badge.resize((max(2, int(badge.width * esc)), max(2, int(badge.height * esc))), Image.Resampling.BICUBIC)
        if abs(giro) > 0.2:
            im = im.rotate(giro, resample=Image.Resampling.BICUBIC, expand=True)
        if op < 0.995:
            r, g, b, a = im.split()
            im = Image.merge('RGBA', (r, g, b, a.point(lambda v: int(v * op))))
        _poner(lienzo, im, cx0 * ancho, cy0 * alto + dy)
        return lienzo
    return _secuencia(clave, total, dibujar)


# ----------------------------------------------------------------------------------------------------------------------- pegatinas
def pegatinas_activas(op):
    """{palabra plegada: id de emoji} = las de fábrica con las del usuario encima."""
    mapa = {_plegar(k): v for k, v in PEGATINAS_POR_DEFECTO.items()}
    for k, v in (op.get('fx_pegatinas_palabras') or {}).items():
        k = _plegar(k)
        if not k:
            continue
        if v:
            mapa[k] = v
        else:
            mapa.pop(k, None)
    return mapa


def coincidencias_pegatinas(palabras, op):
    """[{'ini', 'emoji', 'palabra'}] cada vez que se dice una palabra con pegatina."""
    mapa = pegatinas_activas(op)
    salida = []
    for p in palabras or []:
        w = _plegar(F._texto_palabra(p))
        if w in mapa:
            salida.append({'ini': float(p.get('start', 0.0)), 'emoji': mapa[w], 'palabra': w})
    return salida


def _imagen_emoji(eid):
    from PIL import Image
    try:
        import emojis
        ruta = emojis.ruta_png(eid)
    except Exception:
        ruta = None
    if not ruta or not Path(ruta).is_file():
        return None
    return Image.open(ruta).convert('RGBA')


def _sticker(im, d, ss=2):
    """El emoji en un cuadrado d×d con borde blanco grueso (estilo sticker)."""
    from PIL import Image, ImageFilter
    D = d * ss
    interior = int(D * 0.82)
    e = im.copy()
    e.thumbnail((interior, interior), Image.Resampling.LANCZOS)
    lienzo = Image.new('RGBA', (D, D), (0, 0, 0, 0))
    lienzo.alpha_composite(e, ((D - e.width) // 2, (D - e.height) // 2))
    alfa = lienzo.split()[3]
    borde = alfa.filter(ImageFilter.MaxFilter(max(3, int(D * 0.07) // 2 * 2 + 1))).filter(ImageFilter.GaussianBlur(D * 0.004))
    base = Image.new('RGBA', (D, D), (255, 255, 255, 0))
    base.putalpha(borde.point(lambda v: 255 if v > 90 else 0))
    base.alpha_composite(lienzo)
    return base.resize((d, d), Image.Resampling.LANCZOS)


def secuencia_pegatina(eid, ancho, alto, evitar=None, k=0):
    """El emoji `eid` como sticker (2,4 s) en una esquina libre. None si no hay imagen de ese emoji."""
    from PIL import Image
    img = _imagen_emoji(eid)
    if img is None:
        return None
    cx0, cy0 = _posicion_libre(ancho, alto, evitar, k + 1)
    d = int(min(ancho, alto) * 0.235)
    pegatina = _con_sombra(_sticker(img, d), desenfoque=max(6, d // 16), desp=(0, d // 24))
    total = int(round(DUR_PEGATINA_S * FPS))
    clave = f'pegatina_{eid}_{ancho}x{alto}_{int(cx0 * 100)}-{int(cy0 * 100)}'

    def dibujar(f, n_):
        t = f / float(FPS)
        esc, op, u = _anim_pop(t, DUR_PEGATINA_S, entrada=0.42)
        giro, dy = _giro_y_flote(t, k + 1, u)
        lienzo = Image.new('RGBA', (ancho, alto), (0, 0, 0, 0))
        if op <= 0.004:
            return lienzo
        im = pegatina.resize((max(2, int(pegatina.width * esc)), max(2, int(pegatina.height * esc))), Image.Resampling.BICUBIC)
        if abs(giro) > 0.2:
            im = im.rotate(giro, resample=Image.Resampling.BICUBIC, expand=True)
        if op < 0.995:
            r, g, b, a = im.split()
            im = Image.merge('RGBA', (r, g, b, a.point(lambda v: int(v * op))))
        _poner(lienzo, im, cx0 * ancho, cy0 * alto + dy)
        return lienzo
    return _secuencia(clave, total, dibujar)


# ----------------------------------------------------------------------------------------------------------------------- énfasis: subrayado y círculo a mano
def secuencia_enfasis(tipo, ancho, alto, altura='centro', color=(255, 214, 10)):
    """Un trazo dibujado a mano (1,9 s) que se traza solo: «subrayado» (una línea con un pequeño vaivén) o «circulo» (una elipse abierta). `altura`: arriba / centro / abajo."""
    from PIL import Image, ImageDraw
    cy = ALTURAS.get(altura, ALTURAS['centro'])
    total = int(round(DUR_ENFASIS_S * FPS))
    ss = 2
    rnd = random.Random(7 if tipo == 'subrayado' else 11)
    grosor = max(6, int(min(ancho, alto) * 0.016))
    trazos = []
    if tipo == 'circulo':
        a, b = ancho * 0.30, min(alto * 0.06, ancho * 0.16)
        ang0 = math.radians(205)
        pts = []
        for i in range(0, 121):
            u = i / 120.0
            ang = ang0 + u * math.radians(385)
            r = 1.0 + 0.045 * math.sin(u * 9) + 0.06 * u
            pts.append((ancho * 0.5 + a * r * math.cos(ang), alto * cy + b * r * math.sin(ang)))
        trazos.append((pts, 0.0, 1.0))
    else:
        largo = ancho * 0.56
        x0 = ancho * 0.5 - largo / 2
        pts = []
        for i in range(0, 61):
            u = i / 60.0
            pts.append((x0 + largo * u, alto * cy + math.sin(u * 5.0) * grosor * 0.5 + (u - 0.5) * grosor * 0.8 + rnd.uniform(-0.5, 0.5)))
        trazos.append((pts, 0.0, 0.66))
        pts2 = []                                                    # el segundo trazo, más corto y por debajo (el rasgueo de «remarcar»)
        for i in range(0, 31):
            u = i / 30.0
            pts2.append((x0 + largo * (0.18 + 0.70 * u), alto * cy + grosor * 2.1 + math.sin(u * 4.0) * grosor * 0.25 + (u - 0.5) * grosor * 0.4))
        trazos.append((pts2, 0.52, 1.0))
    clave = f'enfasis_{tipo}_{altura}_{ancho}x{alto}'
    entrada, salida = 0.6, 0.30

    def dibujar(f, n_):
        t = f / float(FPS)
        lienzo = Image.new('RGBA', (ancho * ss, alto * ss), (0, 0, 0, 0))
        g = ImageDraw.Draw(lienzo)
        u_tot = F._suave(min(1.0, t / entrada))
        op = 1.0 if t < DUR_ENFASIS_S - salida else max(0.0, 1.0 - (t - (DUR_ENFASIS_S - salida)) / salida)
        rgba = color + (int(255 * op),)
        for pts, d0, d1 in trazos:
            u = max(0.0, min(1.0, (u_tot - d0) / max(1e-6, d1 - d0)))
            hasta = int(len(pts) * u)
            tramo = [(x * ss, y * ss) for x, y in pts[:hasta]]
            if len(tramo) >= 2:
                g.line(tramo, fill=rgba, width=grosor * ss, joint='curve')
                for x, y in (tramo[0], tramo[-1]):
                    g.ellipse((x - grosor * ss / 2, y - grosor * ss / 2, x + grosor * ss / 2, y + grosor * ss / 2), fill=rgba)
        return lienzo.resize((ancho, alto), Image.Resampling.LANCZOS)
    return _secuencia(clave, total, dibujar)


# ----------------------------------------------------------------------------------------------------------------------- overlays continuos (video en bucle)
def _codificar_video(ruta, fotogramas, ancho, alto, fps=FPS, crf=14):
    """Codifica los fotogramas (iterable de arrays RGB uint8 alto×ancho×3) a un mp4 H.264 con PyAV."""
    import av
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    cont = av.open(str(ruta), 'w')
    try:
        flujo = cont.add_stream('libx264', rate=fps)
        flujo.width, flujo.height = ancho - ancho % 2, alto - alto % 2
        flujo.pix_fmt = 'yuv420p'
        flujo.options = {'crf': str(crf), 'preset': 'veryfast'}
        for arr in fotogramas:
            fr = av.VideoFrame.from_ndarray(arr[:flujo.height, :flujo.width], format='rgb24')
            for paquete in flujo.encode(fr):
                cont.mux(paquete)
        for paquete in flujo.encode():
            cont.mux(paquete)
    finally:
        cont.close()
    return str(ruta)


def clip_overlay(ident, ancho, alto):
    """El mp4 en bucle (4 s) de un overlay continuo a esa resolución, sobre negro (se mezcla en Screen). None si no existe ese overlay."""
    if ident not in {o[0] for o in OVERLAYS}:
        return None
    carpeta = _carpeta_cache(f'overlay_{ident}_{ancho}x{alto}')
    ruta = carpeta / 'clip.mp4'
    if ruta.is_file() and ruta.stat().st_size > 5000:
        return str(ruta)
    import numpy as np
    n = int(round(DUR_OVERLAY_S * FPS))
    # se trabaja a la mitad de resolución y se amplía (el polvo y la luz son suaves; el grano se hace a resolución completa por filas)
    w, h = max(2, ancho // 2), max(2, alto // 2)
    rng = np.random.default_rng(5)

    def fotogramas():
        if ident == 'polvo':
            k = 70
            x0, y0 = rng.random(k) * w, rng.random(k) * h
            vx, vy = rng.normal(0, 14, k), rng.normal(-10, 8, k)          # píxeles por segundo
            rad, fase = rng.uniform(1.2, 3.6, k), rng.random(k) * 6.28
            yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
            for f in range(n):
                t = f / float(FPS)
                lienzo = np.zeros((h, w), np.float32)
                for i in range(k):
                    # la posición es periódica en DUR_OVERLAY_S: el bucle no da saltos
                    x = (x0[i] + vx[i] * DUR_OVERLAY_S * (t / DUR_OVERLAY_S)) % w
                    y = (y0[i] + vy[i] * DUR_OVERLAY_S * (t / DUR_OVERLAY_S)) % h
                    brillo = 0.45 + 0.55 * math.sin(2 * math.pi * (t / DUR_OVERLAY_S) * (1 + i % 2) + fase[i]) ** 2
                    x0c, x1c, y0c, y1c = int(max(0, x - 10)), int(min(w, x + 11)), int(max(0, y - 10)), int(min(h, y + 11))
                    if x1c > x0c and y1c > y0c:
                        d2 = (xx[y0c:y1c, x0c:x1c] - x) ** 2 + (yy[y0c:y1c, x0c:x1c] - y) ** 2
                        lienzo[y0c:y1c, x0c:x1c] += brillo * np.exp(-d2 / (2 * rad[i] ** 2))
                a = np.clip(lienzo, 0, 1) * 255
                mitad = np.stack([a, a * 0.96, a * 0.88], axis=-1).astype(np.uint8)
                yield np.repeat(np.repeat(mitad, 2, axis=0), 2, axis=1)[:alto, :ancho] if mitad.shape[0] * 2 >= alto else mitad
        elif ident == 'grano':
            for f in range(n):
                g = rng.normal(0, 1, (h, w)).astype(np.float32)           # a media resolución: grano más «de película» y 4 veces menos peso
                a = np.clip(34 + g * 22, 0, 255)
                mitad = np.stack([a, a, a], axis=-1).astype(np.uint8)
                yield np.repeat(np.repeat(mitad, 2, axis=0), 2, axis=1)[:alto, :ancho]
        else:   # luz suave: un resplandor cálido que se pasea (periódico)
            yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
            for f in range(n):
                ph = 2 * math.pi * f / n
                cx, cy = w * (0.5 + 0.38 * math.cos(ph)), h * (0.35 + 0.22 * math.sin(ph))
                d = np.sqrt(((xx - cx) / (w * 0.55)) ** 2 + ((yy - cy) / (h * 0.45)) ** 2)
                a = np.clip(1.0 - d, 0, 1) ** 1.8
                brillo = 0.75 + 0.25 * math.sin(ph * 2)
                rgb = np.stack([a * 255 * brillo, a * 165 * brillo, a * 70 * brillo], axis=-1).astype(np.uint8)
                yield np.repeat(np.repeat(rgb, 2, axis=0), 2, axis=1)[:alto, :ancho]

    try:
        return _codificar_video(ruta, fotogramas(), ancho, alto, crf=22 if ident == 'grano' else 14)
    except Exception:
        shutil.rmtree(carpeta, ignore_errors=True)
        return None


# ----------------------------------------------------------------------------------------------------------------------- efectos propios (E1 / E9)
def duracion_archivo(ruta):
    """Lo que dura un archivo de video o animación (s); 0.0 si no se puede leer."""
    ruta = Path(ruta)
    try:
        if ruta.suffix.lower() in {'.gif', '.webp', '.apng', '.png'}:
            from PIL import Image
            with Image.open(ruta) as im:
                n = getattr(im, 'n_frames', 1)
                if n <= 1:
                    return 2.5                                    # una imagen quieta: dura lo que dura una pegatina
                total = 0
                for i in range(n):
                    im.seek(i)
                    total += int(im.info.get('duration', 40) or 40)
                return max(0.1, total / 1000.0)
        return F.duracion_video(ruta)
    except Exception:
        return 0.0


def preparar_propio(entrada, ancho, alto):
    """Un efecto propio -> {'archivo': mp4/mov} (video: se importa tal cual) o {'secuencia': {...}} (imagen o animación: PNG con alpha a la resolución del timeline).
    None si el archivo no existe o no se puede convertir."""
    ruta = Path(str(entrada.get('ruta') or ''))
    if not ruta.is_file():
        return None
    ext = ruta.suffix.lower()
    if ext in EXT_VIDEO:
        return {'archivo': str(ruta)}
    if ext not in EXT_IMAGEN:
        return None
    from PIL import Image, ImageSequence
    clave = f'propio_{_huella(str(ruta), ruta.stat().st_mtime_ns, ancho, alto)}'
    try:
        with Image.open(ruta) as im:
            cuadros = []
            duraciones = []
            for fr in ImageSequence.Iterator(im):
                cuadros.append(fr.convert('RGBA'))
                duraciones.append(max(20, int(fr.info.get('duration', 40) or 40)))
    except Exception:
        return None
    if len(cuadros) <= 1:                                         # imagen quieta: 2,5 s, con una entrada y una salida suaves
        n = int(round(2.5 * FPS))
        indices = [0] * n
    else:
        # se remuestrea a FPS cuadros por segundo según la duración de cada cuadro
        n = max(2, int(round(sum(duraciones) / 1000.0 * FPS)))
        acum, indices, k = 0.0, [], 0
        for f in range(n):
            t = f * 1000.0 / FPS
            while k < len(duraciones) - 1 and acum + duraciones[k] <= t:
                acum += duraciones[k]
                k += 1
            indices.append(k)
    escala = entrada.get('escala') or 'caber'

    def dibujar(f, n_):
        base = cuadros[indices[f]]
        lienzo = Image.new('RGBA', (ancho, alto), (0, 0, 0, 0))
        # tamaño natural (referido a un cuadro de 1080 px de lado corto: un sticker de 400 px ocupa 400 de 1080), sin pasarse del cuadro; «llenar» rellena el cuadro
        e = min(min(ancho, alto) / 1080.0, ancho / base.width, alto / base.height) if escala == 'caber' else max(ancho / base.width, alto / base.height)
        if len(cuadros) <= 1:
            t = f / float(FPS)
            esc, op, _u = _anim_pop(t, n_ / float(FPS))
            e = e * esc
        else:
            op = 1.0
        im = base.resize((max(2, int(base.width * e)), max(2, int(base.height * e))), Image.Resampling.LANCZOS)
        if op < 0.995:
            r, g, b, a = im.split()
            im = Image.merge('RGBA', (r, g, b, a.point(lambda v: int(v * op))))
        _poner(lienzo, im, ancho / 2.0, alto / 2.0)
        return lienzo
    sec = _secuencia(clave, n, dibujar)
    return {'secuencia': sec} if sec else None


# ----------------------------------------------------------------------------------------------------------------------- cierre (outro)
def secuencia_outro(tipo, texto, logo, ancho, alto):
    """El cierre: 'cta' (botón «Sígueme para más»), 'logo' (tu logo con destello) o 'final' (pantalla final oscura con logo y texto). {'patron','n','dur'} o None."""
    from PIL import Image, ImageDraw
    if tipo not in DUR_OUTRO_S:
        return None
    dur = DUR_OUTRO_S[tipo]
    total = int(round(dur * FPS))
    texto = str(texto or '').strip() or 'SÍGUEME PARA MÁS'
    img_logo = None
    if logo and Path(str(logo)).is_file():
        try:
            img_logo = Image.open(str(logo)).convert('RGBA')
        except Exception:
            img_logo = None
    marca = _huella(tipo, texto, str(logo or ''), Path(str(logo)).stat().st_mtime_ns if img_logo is not None else 0)
    clave = f'outro_{tipo}_{ancho}x{alto}_{marca}'
    corto = min(ancho, alto)
    vertical = alto >= ancho
    fuente = _fuente(corto * 0.062)
    caja = ImageDraw.Draw(Image.new('RGBA', (4, 4))).textbbox((0, 0), texto.upper(), font=fuente)
    tw, th = caja[2] - caja[0], caja[3] - caja[1]
    pw, ph = int(tw + corto * 0.12), int(th + corto * 0.075)
    boton = Image.new('RGBA', (pw * 2, ph * 2), (0, 0, 0, 0))
    gb = ImageDraw.Draw(boton)
    gb.rounded_rectangle((0, 0, pw * 2 - 1, ph * 2 - 1), radius=ph, fill=VERDE + (255,), outline=BLANCO + (255,), width=max(4, ph // 14))
    gb.text((pw - tw / 2 - caja[0] + 0, ph - th / 2 - caja[1] - ph * 0.02), texto.upper(), font=fuente, fill=BLANCO + (255,))
    boton = _con_sombra(boton.resize((pw, ph), Image.Resampling.LANCZOS), desenfoque=max(6, ph // 8), desp=(0, ph // 10))
    d_logo = int(corto * (0.42 if tipo != 'cta' else 0.2))
    if img_logo is not None:
        lg = img_logo.copy()
        lg.thumbnail((d_logo, d_logo), Image.Resampling.LANCZOS)
        img_logo = _con_sombra(lg, desenfoque=max(6, d_logo // 16), desp=(0, d_logo // 30), opacidad=0.4)

    def dibujar(f, n_):
        t = f / float(FPS)
        lienzo = Image.new('RGBA', (ancho, alto), (0, 0, 0, 0))
        salida = 0.45
        fuera = 1.0 if t < dur - salida else max(0.0, 1.0 - (t - (dur - salida)) / salida)
        if tipo == 'final':
            vel = int(255 * 0.62 * F._suave(min(1.0, t / 0.6)) * fuera)
            lienzo.alpha_composite(Image.new('RGBA', (ancho, alto), (4, 8, 16, vel)))
        elementos = []                                             # (imagen, cx, cy, retraso)
        cy_texto = alto * (0.74 if tipo == 'cta' else (0.66 if vertical else 0.74))
        if tipo in ('cta', 'final'):
            elementos.append((boton, ancho / 2.0, cy_texto, 0.25 if tipo == 'final' else 0.0))
        if img_logo is not None and tipo in ('logo', 'final', 'cta'):
            cy_logo = alto * (0.45 if tipo != 'cta' else 0.64) if vertical else alto * 0.42
            if tipo == 'cta':
                cy_logo = cy_texto - ph * 1.35 - img_logo.height / 2.0
            elementos.append((img_logo, ancho / 2.0, cy_logo, 0.0))
        for im, cx, cy, retraso in elementos:
            tt = t - retraso
            if tt <= 0:
                continue
            esc, op, u = _anim_pop(tt, dur - retraso, entrada=0.5, salida=0.4)
            pulso = 1.0 + (0.035 * math.sin(2 * math.pi * (tt / 1.1)) if tt > 0.9 and im is boton else 0.0)
            e2 = im.resize((max(2, int(im.width * esc * pulso)), max(2, int(im.height * esc * pulso))), Image.Resampling.BICUBIC)
            r, g, b, a = e2.split()
            e2 = Image.merge('RGBA', (r, g, b, a.point(lambda v: int(v * max(0.0, op * fuera)))))
            _poner(lienzo, e2, cx, cy + 5.0 * math.sin(2 * math.pi * (tt / 2.4)))
        if tipo == 'logo' and img_logo is not None and 0.35 < t < 1.2:               # un destello que cruza el logo
            u = (t - 0.35) / 0.85
            x = ancho * (0.2 + 0.6 * u)
            barra = Image.new('RGBA', (int(corto * 0.10), int(corto * 0.5)), (255, 255, 255, int(90 * math.sin(math.pi * u))))
            barra = barra.rotate(18, expand=True, resample=Image.Resampling.BICUBIC)
            _poner(lienzo, barra, x, alto * 0.45)
        return lienzo
    return _secuencia(clave, total, dibujar)


def sonido_outro(op=None):
    """El sonido del cierre: el que eligió el usuario o un «Power Up» de la biblioteca. Devuelve (ruta, nombre) o (None, None)."""
    op = op or {}
    propio = str(op.get('fx_outro_sonido_archivo') or '')
    if propio and Path(propio).is_file():
        return propio, Path(propio).name
    try:
        from sfx_rules import base_recursos
        carpeta = Path(base_recursos()) / 'sfx_library' / 'Power Up'
        for nombre in ('Power Up 4.wav', 'Power Up 1.wav'):
            if (carpeta / nombre).is_file():
                return str(carpeta / nombre), nombre
    except Exception:
        pass
    return None, None


# ----------------------------------------------------------------------------------------------------------------------- el plan
def _huecos(candidatos, minimo):
    """Las ya ordenadas por tiempo, sin dos más cerca que `minimo` s."""
    salida = []
    for c in sorted(candidatos, key=lambda c: c['ini']):
        if not salida or c['ini'] - salida[-1]['ini'] >= minimo:
            salida.append(c)
    return salida


def planificar_extra(video, palabras, duracion, op, delta=0, cortes_elegidos=None, intro_ini=0.0):
    """Los eventos de los efectos extra (números, pegatinas, énfasis, overlays, propios, outro) para ESTE video. Cada evento: {'tipo', 'ini', 'asset', 'dur'?, 'modo'?, …}."""
    eventos, resumen = [], []
    duracion = float(duracion or 0.0)
    fin_seguro = max(1.0, duracion - 1.0) if duracion else 1e9
    # --- números
    if op.get('fx_numeros') and palabras:
        lista = [n for n in detectar_numeros(palabras) if 0.2 <= n['ini'] <= fin_seguro]
        for k, n in enumerate(lista):
            eventos.append({'tipo': 'numero', 'ini': round(max(0.0, n['ini'] - 0.05), 3), 'asset': f"n{n['n']}", 'n': n['n'], 'dur': DUR_NUMERO_S, 'k': k})
        if lista:
            resumen.append(f'{len(lista)} números')
    # --- pegatinas
    if op.get('fx_pegatinas') and palabras:
        sep, tope = F.CANTIDAD_ICONOS.get(F.desplazar(('pocos', 'normal', 'muchos'), op.get('fx_iconos_cuanto', 'normal'), delta), F.CANTIDAD_ICONOS['normal'])
        cands = [c for c in coincidencias_pegatinas(palabras, op) if 0.8 <= c['ini'] <= fin_seguro]
        elegidas = _huecos(cands, max(DUR_PEGATINA_S + 0.6, sep * 0.4))[:max(2, tope + 2)]
        for k, c in enumerate(elegidas):
            eventos.append({'tipo': 'pegatina', 'ini': round(max(0.0, c['ini'] - 0.05), 3), 'asset': c['emoji'], 'palabra': c['palabra'], 'dur': DUR_PEGATINA_S, 'k': k})
        if elegidas:
            resumen.append(f'{len(elegidas)} pegatinas')
    # --- énfasis (subrayado o círculo en las frases importantes)
    if op.get('fx_enfasis') in {e[0] for e in ENFASIS} and palabras:
        frases = F.elegir_frases(palabras, duracion, 'pocos')
        elegidas = _huecos([{'ini': float(f['ini']) + 0.15} for f in frases], DUR_ENFASIS_S + 1.0)[:6]
        for c in elegidas:
            eventos.append({'tipo': 'enfasis', 'ini': round(c['ini'], 3), 'asset': op['fx_enfasis'], 'altura': op.get('fx_enfasis_altura', 'centro'), 'dur': DUR_ENFASIS_S})
        if elegidas:
            resumen.append(f"{len(elegidas)} {op['fx_enfasis']}s")
    # --- overlay continuo: el bucle de 4 s repetido de punta a punta
    if op.get('fx_overlay') in {o[0] for o in OVERLAYS} and duracion > 1.0:
        fuerza = max(0.1, min(1.0, float(op.get('fx_overlay_fuerza', 0.45)) * (1.0 + 0.35 * delta)))
        t = 0.0
        while t < duracion - 0.05:
            eventos.append({'tipo': 'overlay', 'ini': round(t, 3), 'asset': op['fx_overlay'], 'dur': round(min(DUR_OVERLAY_S, duracion - t), 3), 'modo': 'screen', 'opacidad': round(fuerza * 100, 1)})
            t += DUR_OVERLAY_S
        resumen.append('overlay ' + op['fx_overlay'])
    # --- efectos propios
    for entrada in op.get('fx_propios') or []:
        if not isinstance(entrada, dict) or entrada.get('activo', True) is False or not Path(str(entrada.get('ruta') or '')).is_file():
            continue
        dur = duracion_archivo(entrada['ruta']) or 2.0
        base = {'tipo': 'propio', 'asset': str(entrada.get('id') or Path(entrada['ruta']).stem), 'entrada': entrada, 'modo': entrada.get('modo') or 'screen',
                'opacidad': float(entrada.get('opacidad', 100))}
        uso = entrada.get('uso') or 'intro'
        if uso == 'intro':
            eventos.append(dict(base, ini=round(float(intro_ini), 3), dur=round(dur, 3)))
        elif uso == 'cortes':
            for t in cortes_elegidos or []:
                eventos.append(dict(base, ini=round(max(0.0, float(t) - dur / 2.0), 3), dur=round(dur, 3)))
        elif uso == 'continuo' and duracion > 1.0:
            t = 0.0
            while t < duracion - 0.05:
                eventos.append(dict(base, ini=round(t, 3), dur=round(min(dur, duracion - t), 3)))
                t += max(0.5, dur)
        elif uso == 'palabras' and palabras:
            buscadas = {_plegar(x) for x in (entrada.get('palabras') or []) if _plegar(x)}
            ult = -99.0
            for p in palabras:
                w = _plegar(F._texto_palabra(p))
                t = float(p.get('start', 0.0))
                if w in buscadas and t - ult >= max(dur, 2.0):
                    eventos.append(dict(base, ini=round(t, 3), dur=round(dur, 3)))
                    ult = t
        if any(e.get('tipo') == 'propio' and e.get('asset') == base['asset'] for e in eventos):
            resumen.append('efecto propio «' + base['asset'] + '»')
    # --- outro
    if op.get('fx_outro') in DUR_OUTRO_S and duracion > DUR_OUTRO_S[op['fx_outro']] + 2.0:
        d = DUR_OUTRO_S[op['fx_outro']]
        eventos.append({'tipo': 'outro', 'ini': round(duracion - d - 0.1, 3), 'asset': op['fx_outro'], 'dur': d, 'texto': op.get('fx_outro_texto') or '', 'logo': op.get('fx_outro_logo') or ''})
        if op.get('fx_outro_sonido', True):
            ruta, nombre = sonido_outro(op)
            if ruta:
                real = F.duracion_video(ruta) or 2.0
                eventos.append({'tipo': 'sonido', 'ini': round(duracion - d - 0.1, 3), 'archivo': ruta, 'dur': round(max(0.4, min(d, 3.0, real - 0.05)), 3), 'asset': 'outro · ' + nombre, 'crudo': True})
        resumen.append('cierre ' + op['fx_outro'])
    return eventos, resumen


def preparar(evento, ancho, alto, evitar=None, op=None):
    """Convierte un evento extra en lo que necesita el timeline: devuelve el evento con 'secuencia' o 'archivo' y su 'modo', o None si no se puede preparar."""
    e = dict(evento)
    t = e['tipo']
    if t == 'numero':
        sec = secuencia_numero(e['n'], ancho, alto, evitar, e.get('k', 0))
        e['modo'] = 'normal'
    elif t == 'pegatina':
        sec = secuencia_pegatina(e['asset'], ancho, alto, evitar, e.get('k', 0))
        e['modo'] = 'normal'
    elif t == 'enfasis':
        sec = secuencia_enfasis(e['asset'], ancho, alto, e.get('altura', 'centro'))
        e['modo'] = 'normal'
    elif t == 'broll':
        if not Path(str(e.get('archivo') or '')).is_file():
            return None
        e['modo'] = 'normal'
        return e
    elif t == 'outro':
        sec = secuencia_outro(e['asset'], e.get('texto'), e.get('logo'), ancho, alto)
        e['modo'] = 'normal'
    elif t == 'overlay':
        ruta = clip_overlay(e['asset'], ancho, alto)
        if not ruta:
            return None
        e['archivo'] = ruta
        return e
    elif t == 'propio':
        r = preparar_propio(e['entrada'], ancho, alto)
        if not r:
            return None
        e.pop('entrada', None)
        if r.get('archivo'):
            e['archivo'] = r['archivo']
            return e
        sec = r.get('secuencia')
        if e.get('modo') == 'screen' or e.get('modo') == 'multiply':
            pass                                                # una imagen con alpha en Screen/Multiply también vale
    else:
        return None
    if not sec:
        return None
    e['secuencia'] = sec
    return e


# ----------------------------------------------------------------------------------------------------------------------- zonas que los efectos no deben tapar (E30 / E6)
_ZONAS = {}


def zona_captions(ancho, alto):
    """El rectángulo (fracciones x0, y0, x1, y1) donde suelen ir los captions de GO, según la forma del video."""
    if alto > ancho * 1.2:
        return (0.10, 0.40, 0.90, 0.74)
    if ancho > alto * 1.2:
        return (0.10, 0.62, 0.90, 0.92)
    return (0.10, 0.50, 0.90, 0.85)


def detectar_cara(video, muestras=8):
    """El rectángulo aproximado de la cara de quien habla (fracciones x0, y0, x1, y1) o None. Es una estimación SIN modelos: busca el mayor grupo de color piel (YCbCr) en
    la mitad de arriba de ~8 fotogramas repartidos por el video y se queda con la mediana. En planos sin cara, o si hay mucha piel por todos lados, devuelve None."""
    try:
        import av
        import numpy as np
        cajas = []
        with av.open(str(video)) as c:
            flujo = c.streams.video[0]
            total = float(flujo.duration * flujo.time_base) if flujo.duration else (float(c.duration) / 1_000_000.0 if c.duration else 0.0)
            if total <= 0:
                return None
            for k in range(muestras):
                t = total * (k + 0.5) / muestras
                c.seek(int(t / flujo.time_base), stream=flujo, any_frame=False, backward=True)
                fr = next(c.decode(flujo), None)
                if fr is None:
                    continue
                import rotacion_video as RV                               # v5.5.8: derecho (la cara «arriba» de un video del celular)
                a = RV.derecho_nd(fr.reformat(width=96, height=int(96 * fr.height / max(1, fr.width)), format='rgb24').to_ndarray(),
                                  RV.cuartos(fr)).astype(np.float32)
                r, g, b = a[..., 0], a[..., 1], a[..., 2]
                cb = 128 - 0.168736 * r - 0.331264 * g + 0.5 * b
                cr = 128 + 0.5 * r - 0.418688 * g - 0.081312 * b
                piel = (cb > 77) & (cb < 127) & (cr > 133) & (cr < 173) & (r > 70) & (r > g) & (r > b)
                h, w = piel.shape
                if piel.mean() > 0.45 or piel.mean() < 0.01:
                    continue
                paso = 6                                              # rejilla gruesa: una celda es «piel» si más de la mitad lo es
                gh, gw = h // paso, w // paso
                celdas = piel[:gh * paso, :gw * paso].reshape(gh, paso, gw, paso).mean(axis=(1, 3)) > 0.5
                celdas[int(gh * 0.80):, :] = False                    # la cara no está en el último quinto del cuadro
                visto = np.zeros_like(celdas)
                mejor = []
                for y in range(gh):
                    for x in range(gw):
                        if celdas[y, x] and not visto[y, x]:
                            pila, grupo = [(y, x)], []
                            visto[y, x] = True
                            while pila:
                                cy, cx = pila.pop()
                                grupo.append((cy, cx))
                                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                                    ny, nx = cy + dy, cx + dx
                                    if 0 <= ny < gh and 0 <= nx < gw and celdas[ny, nx] and not visto[ny, nx]:
                                        visto[ny, nx] = True
                                        pila.append((ny, nx))
                            if len(grupo) > len(mejor):
                                mejor = grupo
                if len(mejor) >= 3:
                    ys, xs = [p[0] for p in mejor], [p[1] for p in mejor]
                    cajas.append((min(xs) * paso / w, min(ys) * paso / h, (max(xs) + 1) * paso / w, (max(ys) + 1) * paso / h))
        if len(cajas) < max(3, muestras // 3):
            return None
        m = [float(np.median([b[i] for b in cajas])) for i in range(4)]
        ancho, alto = m[2] - m[0], m[3] - m[1]
        if ancho * alto < 0.004 or ancho > 0.55 or ancho * alto > 0.22:        # un grupo de «piel» más grande que una cara: paredes beige, madera… no es una cara
            return None
        mx, my = ancho * 0.25, alto * 0.30                             # margen: pelo, cuello y hombros
        return (max(0.0, m[0] - mx), max(0.0, m[1] - my), min(1.0, m[2] + mx), min(1.0, m[3] + my * 1.6))
    except Exception:
        return None


def zonas_a_evitar(video, ancho, alto, op):
    """[(x0, y0, x1, y1)] que los iconos, números y pegatinas no deben tapar: la franja de los captions y (si se encuentra) la cara. Se calcula una vez por video."""
    if op.get('fx_evitar', True) is False:
        return []
    clave = (str(video), ancho, alto)
    if clave not in _ZONAS:
        zonas = [zona_captions(ancho, alto)]
        cara = detectar_cara(video) if video else None
        if cara:
            zonas.append(tuple(round(v, 3) for v in cara))
        _ZONAS[clave] = zonas
    return _ZONAS[clave]
