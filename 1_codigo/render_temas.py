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

v5.55: estilo['ajustes'] (opcional, el de «Crea tu estilo») = la letra y los colores elegidos, pintados como en el pack derivado (ajustes_por_rol).
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
# v5.75 (= viral_elementos.comp_corte / comp_shine, ya quietos): rosa con el centro claro y filo oscuro; naranja con franjas amarillas y filo rojo
CORTE_V, BISEL_CORTE_V = [(0.0, (0.99, 0.13, 0.82)), (0.5, (1.0, 0.55, 0.90)), (1.0, (0.99, 0.13, 0.82))], (0.68, 0.10, 0.51)
SHINE_V, BISEL_SHINE_V = [(0.0, (0.99, 0.30, 0.0)), (0.27, (0.99, 0.73, 0.03)), (0.5, (0.99, 0.30, 0.0)), (0.73, (0.99, 0.73, 0.03)), (1.0, (0.99, 0.30, 0.0))], (0.80, 0.16, 0.0)
CAJA_V = {'': (1.0, 0.04, 0.04), 'azul': (0.10, 0.45, 1.0), 'verde': (0.05, 0.85, 0.35), 'naranja': (1.0, 0.50, 0.05)}
ROJO_V = (0.886, 0.024, 0.071)         # v5.78 (= viral_elementos.ROJO_ROJO): la palabra que suena en el Estilo 7
TINTE_V = {'': (1.0, 1.0, 1.0), 'amarillo': (1.0, 0.92, 0.25), 'cian': (0.30, 0.92, 1.0), 'rosa': (1.0, 0.55, 0.80)}
INCLINACION_V = 0.21                   # ShearX de la negrita (cursiva sintética)
# v5.54 «B · Premium» (= viral_elementos.FINA_COLOR / NEGRITA_DEGRADADO / NEGRITA_BRILLO): la fina al 90 %, la negrita blanca → azul hielo con brillo frío
FINA_V = (0.9, 0.9, 0.9)
NEGRITA_V = [(0.0, (0.812, 0.878, 1.0)), (0.6, (1.0, 1.0, 1.0)), (1.0, (1.0, 1.0, 1.0))]
BRILLO_NEGRITA_V = (0.18, 0.38, (0.75, 0.85, 1.0))
# v5.55 (= viral_elementos.EFECTO_RELLENO / EFECTO_BRILLO): Select y Drag como TEMA3 (1)/(2).mp4: blanco roto sin contorno y un brillo blanco suave
# (medido en la referencia: 41/15/9/4/2 de luz a 0,02/0,04/0,06/0,08/0,10 de su alto; esta vista da 39/16/8/3/1); guiones de la caja ~0,15 em y huecos ~0,055
EFECTO_V = 0.955
BRILLO_EFECTO_V = (0.04, 0.14, (1.0, 1.0, 1.0))
# v5.55, medido en el render de Resolve del «select» (5.54): Text+ SUMA (CharacterSpacing − 1) × K_ESP_TEXTPLUS em por letra (−0,046 em por letra con 0,97;
# «× avance» salía un 6 % más ancha), y su caja sale de las métricas de línea: (a los lados del avance, sobre el ascendente, bajo el descendente) en em
K_ESP_TEXTPLUS = 1.53
CAJA_SELECT_V = (0.30, 0.037, 0.043)
# v5.54 «B · Premium»: la sombra ancha de todos (luxe_macro.SOMBRA_PREMIUM: opacidad, bajada × em, desenfoque × em) y el brillo de la principal de
# cada pack «guion» (radio × em, intensidad), comparado con el render de Resolve 21.1.2 (el glow1 de su macro es más suave que el primer cálculo)
SOMBRA_ANCHA = (0.30, 0.10, 0.30)
BRILLO_GUION = {'Referencia': (0.16, 0.32), 'Tema4': (0.16, 0.40), 'Tema5': (0.14, 0.30), 'Tema6': (0.14, 0.30)}


# ------------------------------------------------------------------------------------------------------------------ utilidades
def _rgb255(c):
    """'#rrggbb' o (r, g, b) en 0–1 -> (r, g, b) en 0–255."""
    if isinstance(c, str):
        h = c.lstrip('#')
        return tuple(int(h[k:k + 2], 16) for k in (0, 2, 4))
    return tuple(int(round(max(0.0, min(1.0, float(v))) * 255)) for v in c[:3])


def _fuente(par, px):
    return GC._fuente(tuple(par), max(4, int(round(px))))


def _max_cuadrado(masc, k):
    """v5.84: EXACTAMENTE lo que da `masc.filter(ImageFilter.MaxFilter(k))` (el máximo en un cuadrado k×k con los bordes copiados, como Pillow),
    hecho por filas y luego por columnas con numpy: O(k) por píxel en vez de O(k²), 30-300× más rápido, y suelta el GIL (los bloques se dibujan
    en paralelo). Comparado con Pillow en máscaras de texto, bordes y ruido con k de 3 a 41: idéntico. El contorno del Estilo 7 se llevaba 9 s."""
    r = k // 2
    a = np.asarray(masc, dtype=np.uint8)
    h, w = a.shape
    p = np.pad(a, r, mode='edge')
    filas = p[:, 0:w].copy()
    for d in range(1, k):
        np.maximum(filas, p[:, d:d + w], out=filas)
    res = filas[0:h].copy()
    for d in range(1, k):
        np.maximum(res, filas[d:d + h], out=res)
    return Image.fromarray(res, 'L')


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
        self.rot = 0.0

    def girar(self, grados):
        if abs(grados) > 0.01:
            self.img = self.img.rotate(grados, resample=Image.BICUBIC, expand=True)
            self.rot = float(grados)                 # v5.85 (Premiere con textos): el giro, para girar igual el clip de texto
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
          caja=None, apretar=0.0, brillo=None, sombra2=None, solo_caja=False, dura=None):
    """El sprite de una palabra. em = letra en px; esp = espaciado de letras (× avance); contorno = grosor (× em); sombra = (opacidad, bajada × em,
    desenfoque × em); halo = (radio × em, intensidad); inclinacion = cursiva sintética (× alto); caja = dict(color, pad_x, arriba, abajo (× em),
    punteada, dy (× em, + = arriba), degradado (clara, honda)). Ancla: centro del avance en x, línea de base en y.
    v5.54: apretar = px que el Character Spacing de Fusion quita entre cada dos letras (guion_captions._apretado); brillo = (radio × em, intensidad
    [, color]) del color de la letra (con degradado, el de su mitad); sombra2 = la sombra ancha («B · Premium»), como `sombra`.
    v5.55: solo_caja = solo la caja, en el mismo lienzo y con el mismo anclaje que la palabra (la vista anima la caja del «select» aparte);
    el sprite lleva `total` = el avance de la palabra en px.
    v5.78: dura = (derecha × em, bajada × em, color): la sombra DURA del Estilo 7 (la letra con su contorno, desplazada y sin difuminar)."""
    em = float(em)
    f = _fuente(par, em)
    if f is None:
        return None
    avances = [f.getlength(ch) * esp for ch in txt]
    if apretar and len(txt) > 1:
        # el ancho que mide el planificador (guion_captions.ancho_px: la palabra entera, con su kerning, menos el Character Spacing): letra a letra
        # sin kerning salía más ancha y las palabras se pegaban en la vista
        k = (f.getlength(txt) * esp - apretar * (len(txt) - 1)) / max(1.0, sum(avances))
        avances = [a * k for a in avances]
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
        if caja.get('punteada'):                                     # v5.55: guiones de la referencia (TEMA3 (1).mp4): largos, huecos cortos, puntas redondas
            grosor = max(2, int(em * 0.05))
            guion, hueco = max(6, int(em * 0.15)), max(3, int(em * 0.055))
            radio = grosor / 2.0
            for x0 in np.arange(cx0, cx1, guion + hueco):
                for yy in (cy0, cy1 - grosor):
                    dc.rounded_rectangle([x0, yy, min(cx1, x0 + guion), yy + grosor], radius=radio, fill=col)
            for y0 in np.arange(cy0, cy1, guion + hueco):
                for xx in (cx0, cx1 - grosor):
                    dc.rounded_rectangle([xx, y0, xx + grosor, min(cy1, y0 + guion)], radius=radio, fill=col)
        elif caja.get('degradado'):                                  # v5.54: la pegatina clara arriba, su color en medio y más honda abajo
            clara, honda = caja['degradado']
            alto_c = max(1, int(round(cy1 - cy0)))
            p = np.linspace(0.0, 1.0, alto_c, dtype=np.float32)
            cols = np.array([_rgb255(clara), _rgb255(caja['color']), _rgb255(honda)], dtype=np.float32)
            fila = np.stack([np.interp(p, [0.0, 0.5, 1.0], cols[:, k]) for k in range(3)], axis=1)
            ancho_c = max(1, int(round(cx1 - cx0)))
            banda = Image.fromarray(np.ascontiguousarray(np.broadcast_to(fila[:, None, :], (alto_c, ancho_c, 3)).astype(np.uint8)), 'RGB').convert('RGBA')
            img.alpha_composite(banda, (int(round(cx0)), int(round(cy0))))
        elif caja.get('radio'):                                      # v5.75: la caja redondeada del Tema 3 (radio × alto de la caja)
            dc.rounded_rectangle([cx0, cy0, cx1, cy1], radius=caja['radio'] * (cy1 - cy0), fill=col)
        else:
            dc.rectangle([cx0, cy0, cx1, cy1], fill=col)
    if solo_caja:
        sp = Sprite(_lienzo_centrado(img, pad + total / 2.0, base))
        sp.total = total
        return sp
    for sm in (sombra2, sombra):
        if not sm:
            continue
        op, baja, blur = sm
        s = masc.filter(ImageFilter.GaussianBlur(max(1.0, blur * em))).point(lambda v, op=op: int(v * op))
        capa_s = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        capa_s.putalpha(s)
        desplazada = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        desplazada.alpha_composite(capa_s, (0, int(round(baja * em))))
        img.alpha_composite(desplazada)
    if dura:
        ddx, ddy, col_d = dura
        r_d = max(1, int(round(contorno * em))) if contorno > 0 else 0
        m_d = _max_cuadrado(masc, 2 * r_d + 1) if r_d else masc
        img.alpha_composite(_relleno(m_d, base, cap, color=col_d), (max(0, int(round(ddx * em))), max(0, int(round(ddy * em)))))
    if brillo:
        radio, fuerza = brillo[:2]
        color_b = brillo[2] if len(brillo) > 2 else (min(degradado, key=lambda pc: abs(float(pc[0]) - 0.5))[1] if degradado else color)
        b_m = masc.filter(ImageFilter.GaussianBlur(max(1.5, radio * em))).point(lambda v: int(min(255, v * fuerza * 1.6)))
        img.alpha_composite(_relleno(b_m, base, cap, color=color_b))
    if halo:
        radio, fuerza = halo
        h_m = masc.filter(ImageFilter.GaussianBlur(max(1.5, radio * em))).point(lambda v: int(v * fuerza))
        img.alpha_composite(_relleno(h_m, base, cap, color=color if not degradado else degradado[-1][1]))
    if contorno > 0:
        r = max(1, int(round(contorno * em)))
        borde = _max_cuadrado(masc, 2 * r + 1)
        img.alpha_composite(_relleno(borde, base, cap, color=color_contorno))
    img.alpha_composite(_relleno(masc, base, cap, color=color, degradado=degradado))
    ax = pad + total / 2.0
    if inclinacion:
        k = float(inclinacion)
        extra = int(abs(k) * base) + 2
        ancho = img.size[0] + extra
        img = img.transform((ancho, H), Image.AFFINE, (1, k, -k * base, 0, 1, 0), resample=Image.BICUBIC)
    sp = Sprite(_lienzo_centrado(img, ax, base))
    sp.total = total
    # v5.85 (el usuario: «quiero los textos que se vayan armando en la línea de tiempo» de Premiere): la ficha de la palabra, para que
    # premiere_textos la ponga como un texto editable de Premiere en vez del dibujo (no cambia nada de lo que se dibuja)
    sp.espec = dict(txt=txt, par=tuple(par), em=em, color=color, degradado=degradado, esp=esp, contorno=contorno, color_contorno=color_contorno,
                    sombra=sombra, halo=halo, inclinacion=inclinacion, caja=caja, apretar=apretar, brillo=brillo, sombra2=sombra2, dura=dura)
    return sp


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


# ------------------------------------------------------------------------------------------------------------------ v5.55 letra y color del usuario
# «Crea tu estilo»: estilo['ajustes'] = {'fuente_principal': 'Familia|Estilo' o '', 'fuente_secundaria', 'color_principal': '#RRGGBB' o '',
# 'color_secundario'} (vacío = lo del tema). Principal = la palabra grande (rol 'main'; en Kinetic y VIRAL, fuente_usuario.es_principal: héroe,
# pegatinas serif, negrita y efectos); secundaria = la de arriba y abajo. Se pinta COMO lo deja pack_personalizado en las comps del pack derivado y con
# sus mismas funciones (derivar / derivar_brillo / degradado_premium): el color base del texto pasa a ser el elegido y sus degradados, brillos, halos,
# bisel y caja de pegatina, versiones más claras u hondas del MISMO tono. No cambian: sombras y contornos oscuros, aros y rayas de Kinetic, la caja del
# select, ni el color de los principales Amro del Tema 2 (sí su letra). Sin estilo['ajustes'] todo sale exactamente igual que antes.
def _pp():
    try:
        import pack_personalizado
        return pack_personalizado
    except Exception:
        return None


def _rgb01(c):
    """'#rrggbb' o (r, g, b) en 0–1 -> (r, g, b) en 0–1."""
    if isinstance(c, str):
        return tuple(v / 255.0 for v in _rgb255(c))
    return tuple(float(v) for v in c[:3])


def ajustes_por_rol(estilo):
    """{'main' | 'extra': {'fuente': (familia, estilo) o None, 'color': (r, g, b) en 0–1 o None}} de estilo['ajustes']; {} si no hay nada elegido."""
    aj = (estilo or {}).get('ajustes')
    if not isinstance(aj, dict):
        return {}
    out = {}
    for rol, clave_f, clave_c in (('main', 'fuente_principal', 'color_principal'), ('extra', 'fuente_secundaria', 'color_secundario')):
        partes = [p.strip() for p in str(aj.get(clave_f) or '').split('|')]
        fuente = (partes[0], partes[1] if len(partes) > 1 and partes[1] else 'Regular') if partes[0] else None
        h = str(aj.get(clave_c) or '').strip().lstrip('#')
        if len(h) == 3:
            h = ''.join(ch * 2 for ch in h)
        try:
            color = tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)) if len(h) == 6 else None
        except ValueError:
            color = None
        if fuente or color:
            out[rol] = {'fuente': fuente, 'color': color}
    return out


def rol_de_run(tipo, r):
    """'main' (letra y color principales), 'extra' (los de arriba y abajo) o None (aros y rayas de Kinetic: no son texto), como pack_personalizado.rol_de."""
    if tipo in ('kinetic', 'viral'):
        k = str(r.get('k') or '')
        if k.lower().startswith(('k ring', 'k line')):
            return None
        import fuente_usuario
        return 'main' if fuente_usuario.es_principal({'k': k}) else 'extra'
    return 'main' if r.get('rol') == 'main' else 'extra'


def par_usuario(par, aj):
    """La letra elegida para ese texto si Pillow la encuentra (fuentes_sistema); si no, la del tema."""
    f = (aj or {}).get('fuente')
    if f and _fuente(tuple(f), 100) is not None:
        return tuple(f)
    return tuple(par)


def factor_encaje(par_tema, em_tema, par, em, txt):
    """v5.55 (la letra elegida en «Crea tu estilo» pisaba las palabras vecinas: «Disfrutaremdelritmde»): los planificadores colocan cada palabra
    con las medidas de la letra del TEMA; con otra más ancha o más alta la palabra se reduce lo justo para no ocupar más (ni de ancho ni de alto de
    mayúsculas) que con la del tema. Nunca crece (como fuente_usuario._encajar). 1.0 si es la misma letra o no se puede medir."""
    try:
        if tuple(par) == tuple(par_tema) or not str(txt).strip():
            return 1.0
        ft, fu = _fuente(tuple(par_tema), 100), _fuente(tuple(par), 100)
        if ft is None or fu is None:
            return 1.0
        wt, wu = ft.getlength(txt) * float(em_tema), fu.getlength(txt) * float(em)

        def _cap(f):
            b = f.getbbox('H', anchor='ls')
            return float(b[3] - b[1])
        ht, hu = _cap(ft) * float(em_tema), _cap(fu) * float(em)
        k = min(1.0, wt / wu if wu > 0 else 1.0, ht / hu if hu > 0 else 1.0)
        return max(0.05, k)
    except Exception:
        return 1.0


def anchos(par_tema, em_tema, par, em, txt):
    """(ancho con la letra del tema, ancho con la que se dibuja) de un texto, en px del diseño (aproximado con el avance de Pillow)."""
    try:
        ft = _fuente(tuple(par_tema), 100)
        fu = ft if tuple(par) == tuple(par_tema) else _fuente(tuple(par), 100)
        wt = ft.getlength(txt) * float(em_tema) / 100.0 if ft is not None else None
        wu = fu.getlength(txt) * float(em) / 100.0 if fu is not None else None
        if wt is None or wu is None:
            return None
        return wt, wu
    except Exception:
        return None


def _anotar(sp, par_tema, em_tema, par, em, txt):
    if sp is not None:
        try:
            sp.anchos = anchos(par_tema, em_tema, par, em, txt)
        except Exception:
            pass


def reespaciar(lineas):
    """v5.55: con la letra elegida cada palabra mide otra cosa que la del tema con la que la colocó el planificador; en cada línea (varias palabras a
    la misma altura) se recolocan con los MISMOS huecos que dejó el planificador y la línea centrada donde estaba (sin pisarse ni abrir agujeros).
    lineas = [(centro_x, y, em, ancho_tema, ancho_nuevo, [capas])] (px): van en la misma línea las que están a menos de 0,4 em de alto (las
    pequeñas y las medianas de una línea del Tema 4 se alinean por la base con y algo distintas). Mueve capa['x']; una línea sin cambios no se toca."""
    grupos = []
    for it in sorted(lineas, key=lambda it: it[1]):
        g = grupos[-1] if grupos else None
        if g and abs(it[1] - g[-1][1]) < 0.4 * min(it[2], g[-1][2]):
            g.append(it)
        else:
            grupos.append([it])
    for g in grupos:
        items = [(cx, wt, wu, capas) for cx, _y, _em, wt, wu, capas in g]
        if len(items) < 2 or all(abs(wt - wu) < 0.5 for _cx, wt, wu, _c in items):
            continue
        items = sorted(items, key=lambda it: it[0])
        huecos = [(items[i + 1][0] - items[i + 1][1] / 2.0) - (items[i][0] + items[i][1] / 2.0) for i in range(len(items) - 1)]
        if any(h < -0.25 * min(items[i][1], items[i + 1][1]) for i, h in enumerate(huecos)):
            continue                                               # (se montan a propósito, p. ej. el trazo a mano sobre el héroe: no es una línea)
        centro = ((items[0][0] - items[0][1] / 2.0) + (items[-1][0] + items[-1][1] / 2.0)) / 2.0
        total = sum(it[2] for it in items) + sum(huecos)
        x = centro - total / 2.0
        for i, (cx, _wt, wu, capas) in enumerate(items):
            mover = int(round(x + wu / 2.0 - cx))
            for c in capas:
                c['x'] += mover
            x += wu + (huecos[i] if i < len(huecos) else 0.0)


def _derivar(base, color, nuevo, brillo=False):
    """`color` se dibujó a partir de `base` (el color del texto en el tema): el mismo papel con el color `nuevo` (pack_personalizado.derivar)."""
    pp = _pp()
    b, c, n = _rgb01(base), _rgb01(color), _rgb01(nuevo)
    if pp is None:
        return n
    return tuple(pp.derivar_brillo(b, c, n) if brillo else pp.derivar(b, c, n))


def _base_de(paradas):
    """El color BASE de un degradado: la parada más cercana a la mitad de la letra (pack_personalizado._Retoque.base_texto)."""
    return _rgb01(min(paradas, key=lambda pc: (abs(float(pc[0]) - 0.5), -float(pc[0])))[1])


def degradado_usuario(paradas, nuevo, premium=False):
    """Las paradas de un degradado del tema con el color elegido: el «B · Premium» de fábrica de una principal pasa a degradado_premium(elegido); lo
    demás, cada parada derivada del elegido (más clara u honda, como era respecto del color base)."""
    pp = _pp()
    par = [(float(p), _rgb01(c)) for p, c in paradas]
    base = _base_de(par)
    if premium and pp is not None:
        ref = pp.degradado_premium(base)
        if len(ref) == len(par) and all(abs(p - float(rp)) < 1e-6 and max(abs(a - float(b)) for a, b in zip(c, rc)) <= 0.006
                                        for (p, c), (rp, rc) in zip(par, ref)):
            return [(float(p), _rgb01(c)) for p, c in pp.degradado_premium(_rgb01(nuevo))]
    return [(p, _derivar(base, c, nuevo)) for p, c in par]


def color_usuario(color, degradado, nuevo, premium=False):
    """(color, degradado) de un texto del tema con el color elegido `nuevo` (degradado None = color liso)."""
    if degradado:
        base = _base_de(degradado)
        return _derivar(base, color or base, nuevo), degradado_usuario(degradado, nuevo, premium)
    return _rgb01(nuevo), None


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


def _elemento_guion(estilo, cue, r, s, aj=None):
    """(sprite, centro en el diseño) de una palabra de un pack «guion» (Temas 2, 4, 5, 6). aj (v5.55): la letra y el color elegidos para su rol."""
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
    par_tema = par
    par = par_usuario(par, aj)
    tam = float(d.get('tam') or 0.14)
    try:
        import tema4_planificador as T4
        dis = T4.DISENOS.get(pack)
        esp = (dis['esp_serif'] if rol == 'main' else dis['esp_sans']) if dis else (T4.ESPACIADO if pack == 'Tema4' else 1.0)
    except Exception:
        T4, dis, esp = None, None, 1.0
    txt = str(r.get('texto') or '')
    if d.get('mayus'):
        txt = txt.upper()

    def _em(p):
        try:
            calib = T4._calibrado(p)['em'] if dis else 1.0
        except Exception:
            calib = 1.0
        e = tam * K_PX * float(r.get('zoom') or 1.0) * calib
        if rol == 'main':
            f100 = _fuente(p, 100)
            if f100 is not None and f100.getlength(txt) > 0:
                k_amro = GC.AFINADO['amro_k'].get(int(n)) if (GC.datos_variantes(pack).get(int(n)) or {}).get('amro') else None
                if k_amro:                                         # Amro (Tema 2): el ancho que midió el planificador (k × Inter Black a 100 px)
                    e = 100.0 * k_amro * f100.getlength(str(r.get('texto') or '')) * float(r.get('zoom') or 1.0) / f100.getlength(txt)
                e = min(e, 100.0 * 0.92 * 1080.0 / (f100.getlength(txt) * esp))     # nunca más ancha que el cuadro
        return e
    em = em_tema = _em(par)
    if par != tuple(par_tema):                                     # v5.55: la letra elegida no ocupa más que la del tema (no pisa a sus vecinas)
        em_tema = _em(tuple(par_tema))
        em *= factor_encaje(par_tema, em_tema, par, em, txt)
    color = d.get('color') or '#FFFFFF'
    # v5.54 «B · Premium» (lo que diga el .variantes.json del pack): la principal con el degradado de su color y su brillo; todas con la sombra ancha
    premium = bool((roles.get('main') or {}).get('degradado'))
    degradado = [(float(p), c) for p, c in d['degradado']] if (rol == 'main' and d.get('degradado')) else None
    if (aj or {}).get('color'):
        try:                                                       # v5.55: los principales Amro (Tema 2) conservan su color (pack_personalizado)
            amro = rol == 'main' and bool((GC.datos_variantes(pack).get(int(n)) or {}).get('amro'))
        except Exception:
            amro = False
        if not amro:
            color, degradado = color_usuario(color, degradado, aj['color'], premium=(rol == 'main'))
    brillo = BRILLO_GUION.get(pack) if degradado else None
    extra = dict(degradado=degradado, brillo=brillo, sombra2=SOMBRA_ANCHA if premium else None)
    if pack == 'Tema4':
        sp = texto(txt, par, em * s, color=color, esp=esp, halo=(0.14, 0.7), **extra)            # el de siempre: blanco con halo suave
    elif dis:
        sp = texto(txt, par, em * s, color=color, esp=esp, sombra=(0.6, 0.04, 0.22), halo=(0.10, 0.25), **extra)   # Temas 5/6: la sombra de Remotion y el halo suave del pack
    else:
        # Tema 2 (sombra firme): las letras tan juntas como las deja el Character Spacing del pack en Fusion (lo que mide el planificador,
        # guion_captions.ancho_px). v5.54: sin eso las palabras salían pegadas en la vista («delreconocido»), no en Resolve.
        apretar = (1.0 - GC.AFINADO['espaciado']) * GC.AFINADO['k_espaciado'] * em * s
        sp = texto(txt, par, em * s, color=color, esp=esp, sombra=(0.75, 0.05, 0.08), apretar=apretar, **extra)
    _anotar(sp, par_tema, em_tema, par, em, txt)
    return sp, em, _centro(par)


def _elemento_kinetic(r, s, aj=None):
    import kinetic_captions as KC
    k = str(r.get('k') or '')
    nuevo = (aj or {}).get('color')                                # v5.55: el color elegido para su rol (los aros y las rayas no lo reciben)
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
                            PAL_K.SUBRAYADO_GROSOR * 1080 * s), 0.0, 0.0
    if tipo == 'anillo':
        w, h, g = ANILLO_GEO
        return anillo(ANILLO_K.get(var, (1.0, 0.45, 0.15)), w * 1080 * zx * s, h * 1920 * zy * s, g * 1080 * s), 0.0, 0.0
    if tipo == 'linea':
        w, h = LINEA_GEO
        return raya(LINEA_K.get(var, (1.0, 0.9, 0.05)), w * 1080 * zx * s, h * 1080 * zy * s), 0.0, 0.0
    em = float(r.get('size') or 0.1) * KC.K_PX
    par = par_usuario(e['par'], aj)
    txt = KC.texto_visible(k, str(r.get('texto') or ''))
    em_tema = em
    em *= factor_encaje(e['par'], em, par, em, txt)               # v5.55: la letra elegida no ocupa más que la del tema
    if tipo == 'cinta':
        caja_c, texto_c = CINTA_K.get(var, CINTA_K['amarillo'])
        clara, honda = PAL_K.cinta_degradado(caja_c)
        if nuevo:                                                  # v5.55: la caja del color elegido (su luz y su sombra derivadas); el texto, tinta o blanco
            clara, honda = _derivar(caja_c, clara, nuevo), _derivar(caja_c, honda, nuevo)
            oscuro = (0.2126 * nuevo[0] + 0.7152 * nuevo[1] + 0.0722 * nuevo[2]) > 0.55
            lum_t = 0.2126 * texto_c[0] + 0.7152 * texto_c[1] + 0.0722 * texto_c[2]
            caja_c, texto_c = nuevo, ((PAL_K.TINTA if oscuro else PAL_K.BLANCO) if (lum_t < 0.5) != oscuro else texto_c)
        alto_k, pad_k = e.get('caja', (1.55, 0.5))
        cap, c = KC.CAP.get(e['par'][0], 0.7), _centro(par)        # (la caja de la comp se mide con la letra del tema aunque cambie la del texto)
        # la caja (kinetic_elementos.comp_cinta): alto = alto_k × mayúsculas, centrada 0,03 em por encima del centro del Text+, que está c em sobre la base
        caja = dict(color=caja_c, pad_x=cap * pad_k, arriba=c + 0.03 + cap * alto_k / 2.0, abajo=cap * alto_k / 2.0 - c - 0.03,
                    degradado=(clara, honda))                                  # v5.54 «B · Premium»: la pegatina con el degradado de su color
        # v5.56 (el usuario: «el Tema 1 tiene un efecto sombra, quítaselo»): el Tema 1 va sin sombra oscura, como el pack (Kin 19); quedan el
        # contorno fino y el brillo de su color
        sp = texto(txt, par, em * s, color=texto_c, esp=e.get('esp', 1.0), caja=caja)
    elif k.startswith('k hero'):
        # v5.54 «B · Premium» (= kinetic_elementos.comp_texto premium): el reflejo claro de arriba y el brillo de su color
        grad = GRADIENTES_K.get(var, GRADIENTES_K['blanco'])
        paradas, medio = PAL_K.con_reflejo(grad), PAL_K.color_medio(grad)
        if nuevo:                                                  # v5.55: el degradado y el brillo, del color elegido (base = su parada de la mitad)
            base = _base_de(paradas)
            paradas, medio = degradado_usuario(paradas, nuevo), _derivar(base, medio, nuevo, brillo=True)
        sp = texto(txt, par, em * s, degradado=paradas, esp=e.get('esp', 1.0),
                   contorno=0.02 if var == 'blanco' else 0.0, halo=None, brillo=(0.13, PAL_K.BRILLO_HEROE[0], medio))
    elif k.startswith('k serif'):
        grad = GRADIENTES_K['serif']
        sp = texto(txt, par, em * s, degradado=degradado_usuario(grad, nuevo) if nuevo else grad, contorno=0.03)
    elif k.startswith('k script'):
        grad = GUION_K.get(var, GUION_K['amarillo'])
        sp = texto(txt, par, em * s, degradado=degradado_usuario(grad, nuevo) if nuevo else grad, contorno=0.0 if k.startswith('k script yt') else 0.03)
    else:                                                          # k sup / k label: blanco con contorno oscuro
        sp = texto(txt, par, em * s, color=_rgb01(nuevo) if nuevo else (1, 1, 1), esp=e.get('esp', 1.0), contorno=0.04)
    _anotar(sp, e['par'], em_tema, par, em, txt)
    return sp, em, _centro(par)


def _elemento_viral(r, s, aj=None):
    import viral_captions as VC
    k = str(r.get('k') or '')
    base = VC.base_de(k)
    var = k[len(base):].strip()
    par_tema, esp = VC.CLIPS.get(base, (VC.INTER_18, 1.0))
    par = par_usuario(par_tema, aj)
    nuevo = (aj or {}).get('color')                                # v5.55: el color elegido para su rol (la caja del select no lo recibe)
    if base.startswith('v rojo'):                                  # v5.78: el Estilo 7 (viral_elementos.comp_rojo): Anton blanca y la que suena en rojo
        import linea_planificador as LP
        em = float(r.get('size') or 0.1) * LP.ROJO['k_px']
        txt = str(r.get('texto') or '')
        em_tema = em
        em *= factor_encaje(par_tema, em, par, em, txt)           # (la letra elegida no ocupa más que la Anton)
        activa = base.startswith('v rojo activa')
        color = _rgb01(nuevo) if nuevo else (ROJO_V if activa else (0.98, 0.98, 0.98))
        # contorno negro (Thickness 0,035 ≈ 0,052 em, como la línea: 0,03 → 0,045) y la sombra dura: Offset = Size × (0,022; 0,030) del ANCHO
        k_off = 1080.0 / LP.ROJO['k_px']
        sp = texto(txt, par, em * s, color=color, esp=1.0, contorno=0.052, color_contorno=(0.0, 0.0, 0.0),
                   dura=(0.022 * k_off, 0.030 * k_off, (0.0, 0.0, 0.0)))
        _anotar(sp, par_tema, em_tema, par, em, txt)
        return sp, em, _centro(par)
    if base.startswith('v pila'):                                  # v5.82: el Estilo 4 nuevo (comp_pila): la grande y la que remata abajo en lima con su
        em = float(r.get('size') or 0.06) * VC.K_PX                # brillo, las pequeñas en blanco algo cálido; todas con la sombra negra suave. Como
        txt = str(r.get('texto') or '')                            # la referencia, los mismos px sea cual sea la letra (a 1080): sombra de 12 px con
        em_tema = em                                               # bajada de 5 y brillo de ~22 px al 44 %
        em *= factor_encaje(par_tema, em, par, em, txt)
        lima = base in ('v pila', 'v pila lima')
        color = _rgb01(nuevo) if nuevo else ((0.878, 0.984, 0.345) if lima else (1.0, 1.0, 0.973))
        e_ = max(1.0, em)
        sp = texto(txt, par, em * s, color=color, esp=1.0, apretar=(1.0 - esp) * K_ESP_TEXTPLUS * em * s, sombra=(0.55, 5.0 / e_, 12.0 / e_),
                   halo=(22.0 / e_, 0.44) if lima else None)
        _anotar(sp, par_tema, em_tema, par, em, txt)
        return sp, em, _centro(par)
    if base.startswith(('v ambar', 'v edi')):                      # v5.80: los Estilos 8 (comp_ambar) y 9 (comp_edi): su em por Size, el de su planificador
        import ambar_planificador as AP
        import editorial_planificador as EDP
        ambar = base.startswith('v ambar')
        em = float(r.get('size') or 0.06) * (AP.K_PX if ambar else EDP.K_PX[par_tema])
        txt = str(r.get('texto') or '')
        em_tema = em
        em *= factor_encaje(par_tema, em, par, em, txt)
        if ambar:                                                  # ámbar claro / la clave ámbar, sombra suave (comp_ambar: 0,45, 8)
            color = _rgb01(nuevo) if nuevo else ((0.965, 0.722, 0.337) if base == 'v ambar clave' else (0.949, 0.761, 0.459))
            sp = texto(txt, par, em * s, color=color, esp=1.0, sombra=(0.45, 0.04, 0.18))
        else:                                                      # blanca con la sombra ancha y la corta (comp_edi)
            sp = texto(txt, par, em * s, color=_rgb01(nuevo) if nuevo else (1.0, 1.0, 1.0), esp=1.0, sombra=(0.45, 0.03, 0.10),
                       sombra2=(0.70, 0.04, 0.40))
        _anotar(sp, par_tema, em_tema, par, em, txt)
        return sp, em, _centro(par)
    if base.startswith('v linea'):                                 # v5.75: el Tema 3 de una línea (otra letra: su em por Size es el de linea_planificador)
        import linea_planificador as LP
        em = float(r.get('size') or 0.1) * LP.K_PX
        par = par_usuario(par_tema, aj)
        txt = str(r.get('texto') or '')
        apretar = (1.0 - esp) * K_ESP_TEXTPLUS * em * s
        color_caja = _rgb01(nuevo) if nuevo else ((0.12, 0.36, 1.0) if base.endswith('azul') else (0.075, 0.075, 0.075))
        caja = (dict(color=color_caja, pad_x=0.35 * LP.CAP_EM, arriba=1.53 * LP.CAP_EM, abajo=0.52 * LP.CAP_EM, radio=LP.RADIO_CAJA)
                if base.startswith('v linea activa') else None)
        sp = texto(txt, par, em * s, color=(0.98, 0.98, 0.98), esp=1.0, apretar=apretar, contorno=0.045,
                   color_contorno=(0.078, 0.078, 0.078), sombra=(0.65, 0.0, 0.1), caja=caja)
        _anotar(sp, par_tema, em, par, em, txt)
        return sp, em, _centro(par)
    em = float(r.get('size') or 0.05) * VC.K_PX
    txt = str(r.get('texto') or '')
    em_tema = em
    em *= factor_encaje(par_tema, em, par, em, txt)               # v5.55: la letra elegida no ocupa más que la del tema
    apretar = (1.0 - esp) * K_ESP_TEXTPLUS * em * s                # v5.55: el Character Spacing de Text+ SUMA por letra (medido); la vista lo imita
    if base == 'v negrita':
        grad, brillo = NEGRITA_V, BRILLO_NEGRITA_V
        if nuevo:
            grad, brillo = degradado_usuario(NEGRITA_V, nuevo), BRILLO_NEGRITA_V[:2] + (_derivar(_base_de(NEGRITA_V), BRILLO_NEGRITA_V[2], nuevo, brillo=True),)
        sp = texto(txt, par, em * s, degradado=grad, esp=1.0, apretar=apretar, inclinacion=INCLINACION_V, sombra=(0.5, 0.03, 0.06), brillo=brillo)
    elif base == 'v shatter':
        grad, bisel = SHATTER_V.get(var, SHATTER_V['']), BISEL_V.get(var, BISEL_V[''])
        if nuevo:                                                  # (el bisel es el elemento 2 del Template: un brillo más hondo del mismo tono)
            grad, bisel = degradado_usuario(grad, nuevo), _derivar(_base_de(grad), bisel, nuevo, brillo=True)
        sp = texto(txt, par, em * s, degradado=grad, esp=1.0, apretar=apretar, contorno=0.025, color_contorno=bisel,
                   halo=(0.12, 0.45), sombra=(0.5, 0.03, 0.06))
    elif base in ('v corte', 'v shine'):                           # v5.75 (la vista: ya quieta, sin trozos ni giro)
        grad, bisel = (CORTE_V, BISEL_CORTE_V) if base == 'v corte' else (SHINE_V, BISEL_SHINE_V)
        if nuevo:
            grad, bisel = degradado_usuario(grad, nuevo), _derivar(_base_de(grad), bisel, nuevo, brillo=True)
        sp = texto(txt, par, em * s, degradado=grad, esp=1.0, apretar=apretar, contorno=0.012, color_contorno=bisel, sombra=(0.5, 0.03, 0.06))
    elif base == 'v resalta':                                      # v5.75: la selección del iPhone ya hecha (viral_elementos.RESALTA_*; sin el asa)
        color = _rgb01(nuevo) if nuevo else (0.98, 0.98, 0.98)
        sp = texto(txt, par, em * s, color=color, esp=1.0, apretar=apretar, caja=dict(color=(0.02, 0.0, 0.96), pad_x=0.05, arriba=0.834, abajo=0.17))
    elif base == 'v select':                                       # (su caja punteada es otra capa: _caja_select)
        color = _rgb01(nuevo) if nuevo else (EFECTO_V,) * 3
        brillo = BRILLO_EFECTO_V[:2] + (_derivar((EFECTO_V,) * 3, BRILLO_EFECTO_V[2], nuevo, brillo=True),) if nuevo else BRILLO_EFECTO_V
        sp = texto(txt, par, em * s, color=color, esp=1.0, apretar=apretar, sombra=(0.5, 0.03, 0.06), brillo=brillo)
    elif base == 'v drag':
        relleno = tuple(EFECTO_V * c for c in TINTE_V.get(var, TINTE_V['']))
        color = _rgb01(nuevo) if nuevo else relleno                # (el relleno que arrastra la mano pasa al color elegido)
        brillo = BRILLO_EFECTO_V[:2] + (_derivar(relleno, BRILLO_EFECTO_V[2], nuevo, brillo=True),) if nuevo else BRILLO_EFECTO_V
        sp = texto(txt, par, em * s, color=color, esp=1.0, apretar=apretar, sombra=(0.5, 0.03, 0.06), brillo=brillo)
    else:                                                          # v fina (v5.54: al 90 %)
        color = FINA_V if base == 'v fina' else (1, 1, 1)
        sp = texto(txt, par, em * s, color=_rgb01(nuevo) if nuevo else color, esp=esp, sombra=(0.5, 0.03, 0.06))
    _anotar(sp, par_tema, em_tema, par, em, txt)
    return sp, em, _centro(par)


def _caja_select(r, s, aj=None):
    """v5.55: la caja punteada del «v select», sola, en el mismo lienzo y con el mismo anclaje que su palabra (la vista la anima aparte, como en Resolve:
    crece desde su esquina de arriba a la izquierda cuando acaba de escribirse). Medidas de CAJA_SELECT_V y las métricas de línea de la fuente.
    aj: con la letra elegida la caja se mide con ella (pack_personalizado le pone la letra al Text+ «Caja»); su color no cambia."""
    import viral_captions as VC
    k = str(r.get('k') or '')
    var = k[len(VC.base_de(k)):].strip()
    par_tema, esp = VC.CLIPS['v select']
    par = par_usuario(par_tema, aj)
    em = float(r.get('size') or 0.05) * VC.K_PX
    em *= factor_encaje(par_tema, em, par, em, str(r.get('texto') or ''))     # (la misma reducción que su palabra)
    f = _fuente(par, 200)
    asc, desc = f.getmetrics() if f is not None else (194, 48)
    pad_x, sobre, bajo = CAJA_SELECT_V
    return texto(str(r.get('texto') or ''), par, em * s, esp=1.0, apretar=(1.0 - esp) * K_ESP_TEXTPLUS * em * s, solo_caja=True,
                 caja=dict(color=CAJA_V.get(var, CAJA_V['']), pad_x=pad_x, arriba=asc / 200.0 + sobre, abajo=desc / 200.0 + bajo, punteada=True))


# v5.54: en Resolve cada clip del Tema 2 lleva su propio margen (guion_captions.distribuir solo deja 0,2 espacios entre tramos: «los clips ya llevan
# su propio margen»). Sin él, en la vista los tramos de una línea («con las bandas» + «Glass») salían pegados. MEDIDO en el render del slider (hecho
# con 0,55 espacios): el hueco entre dos tramos era ~0,22 em mayor que el que deja el planificador.
MARGEN_CLIP_EM = 0.22


def _margenes_guion(estilo, cue):
    """{índice del run: desplazamiento en x (fracción del ancho)} que abre los tramos de cada línea pequeña del Tema 2 como en Resolve (la línea sigue centrada)."""
    if (estilo or {}).get('pack') != 'Referencia':
        return {}
    lineas = {}
    for k, r in enumerate(cue.get('runs') or []):
        if isinstance(r, dict) and r.get('rol') != 'main' and str(r.get('texto') or '').strip():
            lineas.setdefault(round(float(r.get('y', 0.5)), 3), []).append((float(r.get('x', 0.5)), k, float(r.get('zoom') or 1.0)))
    mover = {}
    for runs in lineas.values():
        runs.sort()
        for i, (_x, k, z) in enumerate(runs):
            mover[k] = (i - (len(runs) - 1) / 2.0) * MARGEN_CLIP_EM * GC.TAM_PEQUENA * K_PX * z / 1080.0
    return mover


def _capas_tipo(r, s, dx, dy, ini, fin, aj, pack):
    """v5.76: el «v tipo» del Tema 5 (tipo_vista.dibujar): una capa por cada palabra que aparece, cada una con el bloque entero tal como se ve
    desde ese instante; entran y salen de golpe ('seco': la siguiente la reemplaza) salvo la primera (entra en 2 fotogramas) y la última (sale
    con el bloque)."""
    import tipo_vista as TV
    texto = str(r.get('codigo') or r.get('texto') or '')        # (el bloque codificado; 'texto' es lo legible)
    W, H = int(round(1080.0 * s)), int(round(1920.0 * s))
    color = _rgb01(aj['color']) if (aj or {}).get('color') else (1.0, 1.0, 1.0)
    t_clip = max(ini, float(r.get('t', ini)))
    t_fin = float(r['fin']) if isinstance(r.get('fin'), (int, float)) and float(r['fin']) > t_clip else fin
    todo = TV.dibujar(texto, W, H, None, color)
    caja = todo.getchannel('A').getbbox()
    if not caja:
        return []
    estados = [e for e in TV.estados(texto) if t_clip + e < t_fin - 0.02]
    # v5.85 (Premiere con textos editables): las líneas del bloque (texto, letra, tamaño, centro y línea de base RELATIVOS a la esquina de la
    # capa, y cuándo aparece su primera palabra), para que premiere_textos ponga un texto por línea en vez de las imágenes de cada estado
    x0, y0 = dx + caja[0], dy + caja[1]
    lineas_tipo = []
    try:
        import tipo_planificador as TP
        import viral_captions as VC
        for linea in TP.decodificar(texto):
            if not linea:
                continue
            par = linea['par']
            em = linea['size'] * TP.K_PX[par] * W / 1080.0
            base = (1.0 - linea['cy']) * H + TP.CAP[par] * em / 2.0 - TP.DY_EM[par] * em
            aparece = min((float(tt) for tt, ff in linea['tabla'] if ff > 0), default=0.0)
            # la escritura (como tipo_vista._visibles): en cada paso, cuánto mide lo que ya se ve de la línea (px desde su borde izquierdo)
            f_l = VC._fuente(par, em)
            txt_l = linea['texto']
            pasos = []
            for tt, ff in sorted(linea['tabla']):
                if ff <= 0:
                    continue
                vis = txt_l if ff >= 1.0 else txt_l[:int(ff * len(txt_l) + 1e-6)].rstrip()
                pasos.append((t_clip + float(tt), f_l.getlength(vis) if f_l is not None else 0.0))
            lineas_tipo.append({'txt': txt_l, 'par': tuple(par), 'em': em, 'rx': linea['cx'] * W + dx - x0, 'ry': base + dy - y0,
                                't': t_clip + aparece, 'grande': par == TP.GRANDE,
                                'ancho': f_l.getlength(txt_l) if f_l is not None else 0.0, 'pasos': pasos})
    except Exception:
        lineas_tipo = []
    capas = []
    for n, e in enumerate(estados):
        img = TV.dibujar(texto, W, H, e, color).crop(caja)
        if not img.getchannel('A').getbbox():
            continue
        rgb, a = _a_rgba(img, img.getchannel('A'))
        t1 = t_clip + estados[n + 1] if n + 1 < len(estados) else t_fin
        capas.append({'rgb': rgb, 'a': a, 'x': int(round(dx + caja[0])), 'y': int(round(dy + caja[1])), 't0': t_clip + e, 't1': max(t_clip + e + 0.02, t1),
                      'entrada': 0.08 if not capas else 0.0, 'sube': 0.0, 'seco': n + 1 < len(estados),
                      'tipo': 'viral', 'k': 'v tipo', 'rol': 'main', 'pack': pack, 'em': 60.0 * s, 'cue_t0': ini,
                      'tipo_lineas': lineas_tipo, 'tipo_fin': t_fin, 'tipo_color': color, 'tipo_alto': H, 'tipo_ancho': W})
    return capas


def capas_de_cue(estilo, cue, s, dx, dy):
    """Las capas (sprites listos para componer) de los elementos de un cue, en coordenadas del video."""
    tipo = (estilo or {}).get('tipo') or 'guion'
    s, dx, dy = float(s), float(dx), float(dy)                 # (un número de numpy rompe los filtros de Pillow)
    ini, fin = float(cue.get('start') or 0.0), float(cue.get('end') or 0.0)
    capas = []
    mover = _margenes_guion(estilo, cue) if tipo == 'guion' else {}
    por_rol = ajustes_por_rol(estilo)                          # v5.55: la letra y los colores de «Crea tu estilo» ({} = los del tema)
    con_letra = any((v or {}).get('fuente') for v in por_rol.values())
    lineas = []
    for k_run, r in enumerate(cue.get('runs') or []):
        if not isinstance(r, dict):
            continue
        n_antes = len(capas)
        aj = por_rol.get(rol_de_run(tipo, r)) if por_rol else None
        if por_rol and tipo == 'viral' and r.get('k') == 'v rojo':   # v5.78 (= pack_personalizado.ajuste_de_clip): la blanca, letra principal y color del texto pequeño
            aj = {'fuente': (por_rol.get('main') or {}).get('fuente'), 'color': (por_rol.get('extra') or {}).get('color')}
        if tipo == 'viral' and r.get('k') == 'v tipo':             # v5.76: el bloque del Tema 5 (todas sus líneas en un clip): una capa por estado
            try:
                capas += _capas_tipo(r, s, dx, dy, ini, fin, aj, (estilo or {}).get('pack'))
            except Exception:
                pass
            continue
        try:
            if tipo == 'kinetic':
                sp, em, c = _elemento_kinetic(r, s, aj)
            elif tipo == 'viral':
                sp, em, c = _elemento_viral(r, s, aj)
            else:
                if not str(r.get('texto') or '').strip():
                    continue
                sp, em, c = _elemento_guion(estilo, cue, r, s, aj)
        except Exception:
            continue
        if sp is None:
            continue
        sp.girar(float(r.get('rot') or 0.0) if tipo == 'kinetic' else 0.0)
        img = sp.img
        W, H = img.size
        cx = dx + (float(r.get('x', 0.5)) + mover.get(k_run, 0.0)) * 1080.0 * s
        cy = dy + float(r.get('y', 0.5)) * 1920.0 * s + c * em * s          # el ancla del sprite es la línea de base (o el centro, en los trazos)
        rgb, a = _a_rgba(img, img.getchannel('A'))
        t0 = max(ini, float(r.get('t', ini)))
        t1 = float(r['fin']) if isinstance(r.get('fin'), (int, float)) and float(r['fin']) > t0 else fin
        capa = {'rgb': rgb, 'a': a, 'x': int(round(cx - W / 2.0)), 'y': int(round(cy - H / 2.0)), 't0': t0, 't1': max(t0 + 0.05, t1),
                'entrada': ENTRADA_S, 'sube': SUBE_EM * em * s,
                # v5.5.10: qué es cada capa, para que la vista de Creativo (vista_tema.py) la anime como su macro (el MP4 no lo usa)
                'tipo': tipo, 'k': str(r.get('k') or ''), 'rol': r.get('rol'), 'pack': (estilo or {}).get('pack'), 'em': em * s,
                'cue_t0': ini,
                # v5.85: la ficha del texto (None en aros, rayas y trazos) y su giro: premiere_textos lo pone como texto de Premiere
                'espec': getattr(sp, 'espec', None), 'rot': getattr(sp, 'rot', 0.0)}
        if capa['k'].startswith(('v linea activa', 'v rojo')):     # v5.75: la caja del Tema 3 salta de palabra en palabra (corte seco, como el clip); v5.78: el Estilo 7, corte seco
            capa.update(entrada=0.0, sube=0.0)
            if capa['k'].startswith('v rojo'):
                capa['seco'] = True                                 # v5.80: el Estilo 7 se va de golpe (blancas y roja a la vez; render_sin_resolve sin SALIDA_S)
        total = getattr(sp, 'total', 0.0)
        if tipo == 'viral' and total:                               # v5.55: dónde va la palabra dentro del sprite y cuántas letras «mide» (lo que escribe el «select»)
            capa.update(tinta=(0.5 - total / (2.0 * W), 0.5 + total / (2.0 * W)), letras=total / (0.62 * em * s))
        capas.append(capa)
        if tipo == 'viral' and capa['k'].startswith('v select'):   # v5.55: la caja punteada del «select», capa aparte encima de la palabra
            try:
                sc = _caja_select(r, s, aj)
                rgb_c, a_c = _a_rgba(sc.img, sc.img.getchannel('A'))
                Wc, Hc = sc.img.size
                capas.append(dict(capa, rgb=rgb_c, a=a_c, x=int(round(cx - Wc / 2.0)), y=int(round(cy - Hc / 2.0)), parte='caja', espec=None))
            except Exception:
                pass
        an = getattr(sp, 'anchos', None) if con_letra else None
        if an:                                                     # (para reespaciar la línea con la letra elegida)
            lineas.append((cx, float(r.get('y', 0.5)) * 1920.0 * s, max(1.0, em * s), an[0] * s, an[1] * s, capas[n_antes:]))
    if lineas:
        reespaciar(lineas)
    return capas
