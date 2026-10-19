# CineCaptions · By Cinema Productions
# 1_codigo/render_temas.py — GO sin DaVinci Resolve con CUALQUIER tema (v5.5.8): cómo se dibuja cada uno con Pillow a partir de los mismos datos que lee Resolve.
"""
render_temas.py
---------------
Pedido (2026-10-15): «Necesito que funcione para todos los temas sin necesidad de Resolve». render_sin_resolve.py graba el MP4; aquí se convierte cada
elemento de los cues (los MISMOS que se escriben para Resolve: posición, tamaño, giro y momento de cada palabra) en un sprite RGBA ya rasterizado:

    Temas 2, 4, 5 y 6 («guion»: Referencia, Tema4, Tema5, Tema6)  cada run = una palabra con el rol de su variante (principal / arriba / abajo): tipografía,
        color y mayúsculas del .variantes.json del pack; letra = Size del rol × K_PX × zoom (los Temas 5/6, × tema4_planificador.CALIBRADO). Temas 5/6: la frase
        clave en su serif y su color; una sombra fina como en Remotion.
    Tema 1 (Kinetic)  cada run = un elemento del pack («k hero lima», «k tape amarillo», «k ring rosa», «k line lima»…): tipografía de kinetic_captions._espec,
        degradado / cinta / anillo / subrayado con los colores de generador_packs/kinetic_elementos.py, giro (rot) y zoom de los trazos (zx, zy).
    Tema 3 (VIRAL)  «v fina» (Inter 18pt Medium), «v negrita» (Inter 28pt ExtraBold con cursiva sintética) y los efectos «v shatter / select / drag» (Inter 28pt
        Black: degradado con bisel, caja punteada, relleno teñido) con los colores de generador_packs/viral_elementos.py; letra = size × viral_captions.K_PX.

El centro del Text+ de Resolve = (x, y) del run: la línea de base queda (asc − desc) / 2 em por debajo (Fusion centra la caja de la línea; Inter: 0,364 =
tema4_planificador.CENTRO_CAP, medido). Las animaciones de los macros de Fusion no se copian: cada elemento entra con un fundido corto y sube un poco.

    capas_de_cue(estilo, cue, s, dx, dy) -> [{'rgb', 'a', 'x', 'y', 't0', 't1', 'entrada', 'sube'}]   (coordenadas del video: diseño × s + (dx, dy))
"""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import guion_captions as GC

K_PX = 640.0
ENTRADA_S = 0.12               # el fundido de entrada de cada elemento
SUBE_EM = 0.10                 # y lo que sube mientras entra (× su letra)

# --- Kinetic: deben coincidir con 2_recursos/generador_packs/kinetic_elementos.py (los colores de cada clip del pack) --------------------------------
import kinetic_paleta as PAL_K                  # v5.5.13: los colores del Tema 1 (neón) salen de la misma paleta que el pack
GRADIENTES_K = PAL_K.GRADIENTES
CINTA_K = PAL_K.CINTA
GUION_K = PAL_K.GUION
ANILLO_K = PAL_K.ANILLO
LINEA_K = PAL_K.LINEA
ANILLO_GEO = (0.42, 0.16, 0.012)       # ancho (× ancho del cuadro), alto (× alto del cuadro), grosor (× ancho) a zoom 1
LINEA_GEO = (0.34, 0.0075)             # ancho (× ancho), alto (× ancho)

# --- VIRAL: deben coincidir con 2_recursos/generador_packs/viral_elementos.py ---------------------------------------------------------------------------
SHATTER_V = {'': [(0.0, (0.10, 0.52, 0.98)), (0.5, (0.42, 0.74, 1.0)), (1.0, (0.78, 0.92, 1.0))],
             'rosa': [(0.0, (0.93, 0.18, 0.55)), (0.5, (1.0, 0.46, 0.73)), (1.0, (1.0, 0.84, 0.93))],
             'lima': [(0.0, (0.30, 0.74, 0.08)), (0.5, (0.60, 0.94, 0.28)), (1.0, (0.88, 1.0, 0.70))],
             'oro': [(0.0, (0.93, 0.50, 0.03)), (0.5, (1.0, 0.77, 0.24)), (1.0, (1.0, 0.94, 0.68))]}
BISEL_V = {'': (0.05, 0.38, 0.86), 'rosa': (0.72, 0.05, 0.34), 'lima': (0.18, 0.50, 0.04), 'oro': (0.68, 0.32, 0.0)}
CAJA_V = {'': (1.0, 0.04, 0.04), 'azul': (0.10, 0.45, 1.0), 'verde': (0.05, 0.85, 0.35), 'naranja': (1.0, 0.50, 0.05)}
TINTE_V = {'': (1.0, 1.0, 1.0), 'amarillo': (1.0, 0.92, 0.25), 'cian': (0.30, 0.92, 1.0), 'rosa': (1.0, 0.55, 0.80)}
INCLINACION_V = 0.21                   # ShearX de la negrita (cursiva sintética)


# ------------------------------------------------------------------------------------------------------------------ utilidades
def _rgb255(c):
    """'#rrggbb' o (r, g, b) en 0–1 -> (r, g, b) en 0–255."""
    if isinstance(c, str):
        h = c.lstrip('#')
        return tuple(int(h[k:k + 2], 16) for k in (0, 2, 4))
    return tuple(int(round(max(0.0, min(1.0, float(v))) * 255)) for v in c[:3])


def _fuente(par, px):
    return GC._fuente(tuple(par), max(4, int(round(px))))


def _centro(par):
    """Lo que la línea de base queda por debajo del centro del Text+ (× la letra): (asc − desc) / 2 de hhea (Fusion centra la caja de la línea)."""
    f = _fuente(par, 200)
    if f is None:
        return 0.364
    asc, desc = f.getmetrics()
    return (asc - desc) / 400.0


def _a_rgba(img_rgb, alfa):
    arr = np.asarray(img_rgb, dtype=np.float32)
    a = np.asarray(alfa, dtype=np.float32)[..., None] / 255.0
    return arr[..., :3].copy(), a


class Sprite:
    """Un elemento ya rasterizado (RGBA en una imagen PIL) con su punto de anclaje en el CENTRO del lienzo: girar no lo mueve."""

    def __init__(self, img):
        self.img = img

    def girar(self, grados):
        if abs(grados) > 0.01:
            self.img = self.img.rotate(grados, resample=Image.BICUBIC, expand=True)
        return self


def _lienzo_centrado(img, ax, ay):
    """Pone `img` en un lienzo con (ax, ay) en el centro exacto."""
    w, h = img.size
    mx, my = max(ax, w - ax), max(ay, h - ay)
    W, H = int(math.ceil(2 * mx)) + 2, int(math.ceil(2 * my)) + 2
    out = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    out.alpha_composite(img, (int(round(W / 2.0 - ax)), int(round(H / 2.0 - ay))))
    return out


def _relleno(mascara, base_y, alto_tinta, color=None, degradado=None):
    """La capa de color de unas letras: color liso o degradado vertical (parada 0 = la línea de base, 1 = la altura de las mayúsculas)."""
    w, h = mascara.size
    if degradado:
        ys = np.arange(h, dtype=np.float32)
        p = np.clip((base_y - ys) / max(1.0, alto_tinta), 0.0, 1.0)
        pos = [float(q) for q, _c in degradado]
        cols = np.array([_rgb255(c) for _q, c in degradado], dtype=np.float32)
        fila = np.stack([np.interp(p, pos, cols[:, k]) for k in range(3)], axis=1)
        arr = np.broadcast_to(fila[:, None, :], (h, w, 3)).astype(np.uint8)
        capa = Image.fromarray(np.ascontiguousarray(arr), 'RGB').convert('RGBA')
    else:
        capa = Image.new('RGBA', (w, h), _rgb255(color or (1, 1, 1)) + (255,))
    capa.putalpha(mascara)
    return capa


def texto(txt, par, em, color=(1, 1, 1), degradado=None, esp=1.0, contorno=0.0, color_contorno=(0, 0, 0), sombra=None, halo=None, inclinacion=0.0,
          caja=None):
    """El sprite de una palabra. em = letra en px; esp = espaciado de letras (× avance); contorno = grosor (× em); sombra = (opacidad, bajada × em,
    desenfoque × em); halo = (radio × em, intensidad); inclinacion = cursiva sintética (× alto); caja = dict(color, pad_x, arriba, abajo (× em),
    punteada, dy (× em, + = arriba)). Ancla: centro del avance en x, línea de base en y."""
    em = float(em)
    f = _fuente(par, em)
    if f is None:
        return None
    avances = [f.getlength(ch) * esp for ch in txt]
    total = sum(avances)
    asc, desc = f.getmetrics()
    pad = int(em * (0.9 + abs(inclinacion))) + 6
    W, H = int(total + 2 * pad) + 1, int(asc + desc + 2 * pad) + 1
    base = float(pad + asc)
    masc = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(masc)
    x = float(pad)
    for ch, a in zip(txt, avances):
        d.text((x, base), ch, font=f, fill=255, anchor='ls')
        x += a
    cap = em * 0.72
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    if caja:
        cx0, cx1 = pad - caja.get('pad_x', 0.3) * em, pad + total + caja.get('pad_x', 0.3) * em
        dy = caja.get('dy', 0.0) * em
        cy0, cy1 = base - caja.get('arriba', 1.0) * em - dy, base + caja.get('abajo', 0.3) * em - dy
        dc = ImageDraw.Draw(img)
        col = _rgb255(caja['color']) + (255,)
        if caja.get('punteada'):
            grosor = max(2, int(em * 0.05))
            paso = max(6, int(em * 0.16))
            for x0 in np.arange(cx0, cx1, paso * 2):
                for yy in (cy0, cy1 - grosor):
                    dc.rectangle([x0, yy, min(cx1, x0 + paso), yy + grosor], fill=col)
            for y0 in np.arange(cy0, cy1, paso * 2):
                for xx in (cx0, cx1 - grosor):
                    dc.rectangle([xx, y0, xx + grosor, min(cy1, y0 + paso)], fill=col)
        else:
            dc.rectangle([cx0, cy0, cx1, cy1], fill=col)
    if sombra:
        op, baja, blur = sombra
        s = masc.filter(ImageFilter.GaussianBlur(max(1.0, blur * em))).point(lambda v: int(v * op))
        capa_s = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        capa_s.putalpha(s)
        desplazada = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        desplazada.alpha_composite(capa_s, (0, int(round(baja * em))))
        img.alpha_composite(desplazada)
    if halo:
        radio, fuerza = halo
        h_m = masc.filter(ImageFilter.GaussianBlur(max(1.5, radio * em))).point(lambda v: int(v * fuerza))
        img.alpha_composite(_relleno(h_m, base, cap, color=color if not degradado else degradado[-1][1]))
    if contorno > 0:
        r = max(1, int(round(contorno * em)))
        borde = masc.filter(ImageFilter.MaxFilter(2 * r + 1))
        img.alpha_composite(_relleno(borde, base, cap, color=color_contorno))
    img.alpha_composite(_relleno(masc, base, cap, color=color, degradado=degradado))
    ax = pad + total / 2.0
    if inclinacion:
        k = float(inclinacion)
        extra = int(abs(k) * base) + 2
        ancho = img.size[0] + extra
        img = img.transform((ancho, H), Image.AFFINE, (1, k, -k * base, 0, 1, 0), resample=Image.BICUBIC)
    return Sprite(_lienzo_centrado(img, ax, base))


def anillo(color, ancho_px, alto_px, grosor_px):
    W, H = int(ancho_px + 2 * grosor_px + 4), int(alto_px + 2 * grosor_px + 4)
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse([grosor_px, grosor_px, W - grosor_px - 1, H - grosor_px - 1], outline=_rgb255(color) + (255,), width=max(1, int(grosor_px)))
    return Sprite(_lienzo_centrado(img, W / 2.0, H / 2.0))


def trazo_a_mano(color, puntos, ancho_px, alto_px, nominal, grosor_px):
    """v5.5.13 (neón): el círculo, el lazo o el subrayado a mano (kinetic_paleta.puntos_*), escalado a ancho_px × alto_px como lo escala Resolve (zx, zy)."""
    nw, nh = nominal
    fx, fy = ancho_px / max(1e-6, nw), alto_px / max(1e-6, nh)
    xs = [p[0] * fx for p in puntos]
    ys = [p[1] * fy for p in puntos]
    m = grosor_px + 4
    W, H = int(max(xs) - min(xs) + 2 * m), int(max(ys) - min(ys) + 2 * m)
    img = Image.new('RGBA', (max(2, W), max(2, H)), (0, 0, 0, 0))
    pts = [(x - min(xs) + m, y - min(ys) + m) for x, y in zip(xs, ys)]
    ImageDraw.Draw(img).line(pts, fill=_rgb255(color) + (255,), width=max(1, int(grosor_px)), joint='curve')
    return Sprite(_lienzo_centrado(img, -min(xs) + m, -min(ys) + m))


def raya(color, ancho_px, alto_px):
    W, H = int(ancho_px) + 4, int(max(2, alto_px)) + 4
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle([2, 2, W - 3, H - 3], radius=max(1, int(alto_px / 2)), fill=_rgb255(color) + (255,))
    return Sprite(_lienzo_centrado(img, W / 2.0, H / 2.0))


# ------------------------------------------------------------------------------------------------------------------ cada tema
def _variantes(pack):
    """{n: {rol: {'f1', 'tam', 'color', 'mayus'}}} del .variantes.json del pack (vertical)."""
    import json
    from pathlib import Path

    import plantillas
    try:
        p = plantillas.buscar_pack(pack)
        drb = Path(p.ruta_drb('v'))
        crudo = json.loads(drb.with_name(drb.stem + '.variantes.json').read_text(encoding='utf-8'))
        return {int(n): (v.get('roles') or {}) for n, v in crudo.items()}
    except Exception:
        return {}


_CACHE_VAR = {}


def _elemento_guion(estilo, cue, r, s):
    """(sprite, centro en el diseño) de una palabra de un pack «guion» (Temas 2, 4, 5, 6)."""
    pack = estilo.get('pack') or 'Tema4'
    if pack not in _CACHE_VAR:
        _CACHE_VAR[pack] = _variantes(pack)
    variantes = _CACHE_VAR[pack]
    rol = r.get('rol') if r.get('rol') in ('main', 'context', 'complement') else 'context'
    n = r.get('estilo') or cue.get('estilo') or 1
    roles = variantes.get(int(n)) or next(iter(variantes.values()), {})
    d = roles.get(rol) or roles.get('main') or {}
    par = tuple(d.get('f1') or ('Poppins', 'Bold'))
    if d.get('f1') is None and rol == 'main':
        par = ('Inter', 'Black')                                   # (los presets de Amro llevan su tipografía dentro del macro)
    tam = float(d.get('tam') or 0.14)
    try:
        import tema4_planificador as T4
        dis = T4.DISENOS.get(pack)
        calib = T4._calibrado(par)['em'] if dis else 1.0
        esp = (dis['esp_serif'] if rol == 'main' else dis['esp_sans']) if dis else (T4.ESPACIADO if pack == 'Tema4' else 1.0)
    except Exception:
        dis, calib, esp = None, 1.0, 1.0
    em = tam * K_PX * float(r.get('zoom') or 1.0) * calib
    txt = str(r.get('texto') or '')
    if d.get('mayus'):
        txt = txt.upper()
    if rol == 'main':
        f100 = _fuente(par, 100)
        if f100 is not None and f100.getlength(txt) > 0:
            k_amro = GC.AFINADO['amro_k'].get(int(n)) if (GC.datos_variantes(pack).get(int(n)) or {}).get('amro') else None
            if k_amro:                                             # Amro (Tema 2): el ancho que midió el planificador (k × Inter Black a 100 px)
                em = 100.0 * k_amro * f100.getlength(str(r.get('texto') or '')) * float(r.get('zoom') or 1.0) / f100.getlength(txt)
            em = min(em, 100.0 * 0.92 * 1080.0 / (f100.getlength(txt) * esp))     # nunca más ancha que el cuadro
    color = d.get('color') or '#FFFFFF'
    if pack == 'Tema4':
        sp = texto(txt, par, em * s, color=color, esp=esp, halo=(0.14, 0.7))            # el de siempre: blanco con halo suave
    elif dis:
        sp = texto(txt, par, em * s, color=color, esp=esp, sombra=(0.6, 0.04, 0.22), halo=(0.10, 0.25))   # Temas 5/6: la sombra de Remotion y el halo suave del pack
    else:
        sp = texto(txt, par, em * s, color=color, esp=esp, sombra=(0.75, 0.05, 0.08))  # Tema 2: sombra firme
    return sp, em, _centro(par)


def _elemento_kinetic(r, s):
    import kinetic_captions as KC
    k = str(r.get('k') or '')
    e = KC._espec(k)
    var = k.split(' ')[-1] if ' ' in k else ''
    tipo = e.get('tipo')
    zx, zy = float(r.get('zx') or 1.0), float(r.get('zy') or 1.0)
    if tipo == 'trazo':
        nw, nh = PAL_K.TRAZO_NOMINAL
        return trazo_a_mano(ANILLO_K.get(var, PAL_K.LIMA), PAL_K.puntos_circulo(lazo='lazo' in k), nw * 1080 * zx * s, nh * 1080 * zy * s,
                            (nw, nh), PAL_K.TRAZO_GROSOR * 1080 * s * (zx + zy) / 2.0), 0.0, 0.0
    if tipo == 'linea' and e.get('curva'):
        nw = PAL_K.SUBRAYADO_NOMINAL
        return trazo_a_mano(LINEA_K.get(var, PAL_K.LIMA), PAL_K.puntos_subrayado(), nw * 1080 * zx * s, nw * 1080 * zy * s, (nw, nw),
                            PAL_K.TRAZO_GROSOR * 1080 * s * zx), 0.0, 0.0
    if tipo == 'anillo':
        w, h, g = ANILLO_GEO
        return anillo(ANILLO_K.get(var, (1.0, 0.45, 0.15)), w * 1080 * zx * s, h * 1920 * zy * s, g * 1080 * s), 0.0, 0.0
    if tipo == 'linea':
        w, h = LINEA_GEO
        return raya(LINEA_K.get(var, (1.0, 0.9, 0.05)), w * 1080 * zx * s, h * 1080 * zy * s), 0.0, 0.0
    em = float(r.get('size') or 0.1) * KC.K_PX
    par = e['par']
    txt = KC.texto_visible(k, str(r.get('texto') or ''))
    if tipo == 'cinta':
        caja_c, texto_c = CINTA_K.get(var, CINTA_K['amarillo'])
        alto_k, pad_k = e.get('caja', (1.55, 0.5))
        cap, c = KC.CAP.get(par[0], 0.7), _centro(par)
        # la caja (kinetic_elementos.comp_cinta): alto = alto_k × mayúsculas, centrada 0,03 em por encima del centro del Text+, que está c em sobre la base
        caja = dict(color=caja_c, pad_x=cap * pad_k, arriba=c + 0.03 + cap * alto_k / 2.0, abajo=cap * alto_k / 2.0 - c - 0.03)
        sp = texto(txt, par, em * s, color=texto_c, esp=e.get('esp', 1.0), caja=caja, sombra=(0.5, 0.03, 0.05))
    elif k.startswith('k hero'):
        sp = texto(txt, par, em * s, degradado=GRADIENTES_K.get(var, GRADIENTES_K['blanco']), esp=e.get('esp', 1.0),
                   contorno=0.02 if var == 'blanco' else 0.0, sombra=(0.8, 0.03, 0.05), halo=None)
    elif k.startswith('k serif'):
        sp = texto(txt, par, em * s, degradado=GRADIENTES_K['serif'], contorno=0.03, sombra=(0.8, 0.03, 0.05))
    elif k.startswith('k script'):
        sp = texto(txt, par, em * s, degradado=GUION_K.get(var, GUION_K['amarillo']), contorno=0.0 if k.startswith('k script yt') else 0.03, sombra=(0.8, 0.03, 0.05))
    else:                                                          # k sup / k label: blanco con contorno oscuro
        sp = texto(txt, par, em * s, color=(1, 1, 1), esp=e.get('esp', 1.0), contorno=0.04, sombra=(0.8, 0.03, 0.05))
    return sp, em, _centro(par)


def _elemento_viral(r, s):
    import viral_captions as VC
    k = str(r.get('k') or '')
    base = VC.base_de(k)
    var = k[len(base):].strip()
    par, esp = VC.CLIPS.get(base, (VC.INTER_18, 1.0))
    em = float(r.get('size') or 0.05) * VC.K_PX
    txt = str(r.get('texto') or '')
    if base == 'v negrita':
        sp = texto(txt, par, em * s, color=(1, 1, 1), esp=esp, inclinacion=INCLINACION_V, sombra=(0.5, 0.03, 0.06))
    elif base == 'v shatter':
        sp = texto(txt, par, em * s, degradado=SHATTER_V.get(var, SHATTER_V['']), esp=esp, contorno=0.025, color_contorno=BISEL_V.get(var, BISEL_V['']),
                   halo=(0.12, 0.45), sombra=(0.5, 0.03, 0.06))
    elif base == 'v select':
        sp = texto(txt, par, em * s, color=(1, 1, 1), esp=esp, sombra=(0.5, 0.03, 0.06),
                   caja=dict(color=CAJA_V.get(var, CAJA_V['']), pad_x=0.18, arriba=0.73 * (1.0 + VC.SOBRESALE['v select'][0]), abajo=0.73 * VC.SOBRESALE['v select'][1],
                             punteada=True))
    elif base == 'v drag':
        tinte = TINTE_V.get(var, TINTE_V[''])
        sp = texto(txt, par, em * s, color=tinte, esp=esp, sombra=(0.5, 0.03, 0.06))
    else:
        sp = texto(txt, par, em * s, color=(1, 1, 1), esp=esp, sombra=(0.5, 0.03, 0.06))
    return sp, em, _centro(par)


def capas_de_cue(estilo, cue, s, dx, dy):
    """Las capas (sprites listos para componer) de los elementos de un cue, en coordenadas del video."""
    tipo = (estilo or {}).get('tipo') or 'guion'
    s, dx, dy = float(s), float(dx), float(dy)                 # (un número de numpy rompe los filtros de Pillow)
    ini, fin = float(cue.get('start') or 0.0), float(cue.get('end') or 0.0)
    capas = []
    for r in cue.get('runs') or []:
        if not isinstance(r, dict):
            continue
        try:
            if tipo == 'kinetic':
                sp, em, c = _elemento_kinetic(r, s)
            elif tipo == 'viral':
                sp, em, c = _elemento_viral(r, s)
            else:
                if not str(r.get('texto') or '').strip():
                    continue
                sp, em, c = _elemento_guion(estilo, cue, r, s)
        except Exception:
            continue
        if sp is None:
            continue
        sp.girar(float(r.get('rot') or 0.0) if tipo == 'kinetic' else 0.0)
        img = sp.img
        W, H = img.size
        cx = dx + float(r.get('x', 0.5)) * 1080.0 * s
        cy = dy + float(r.get('y', 0.5)) * 1920.0 * s + c * em * s          # el ancla del sprite es la línea de base (o el centro, en los trazos)
        rgb, a = _a_rgba(img, img.getchannel('A'))
        t0 = max(ini, float(r.get('t', ini)))
        t1 = float(r['fin']) if isinstance(r.get('fin'), (int, float)) and float(r['fin']) > t0 else fin
        capas.append({'rgb': rgb, 'a': a, 'x': int(round(cx - W / 2.0)), 'y': int(round(cy - H / 2.0)), 't0': t0, 't1': max(t0 + 0.05, t1),
                      'entrada': ENTRADA_S, 'sube': SUBE_EM * em * s,
                      # v5.5.10: qué es cada capa, para que la vista de Creativo (vista_tema.py) la anime como su macro (el MP4 no lo usa)
                      'tipo': tipo, 'k': str(r.get('k') or ''), 'rol': r.get('rol'), 'pack': (estilo or {}).get('pack'), 'em': em * s,
                      'cue_t0': ini})
    return capas
