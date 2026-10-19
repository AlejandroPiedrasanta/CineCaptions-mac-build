# CineCaptions · By Cinema Productions
# 1_codigo/kinetic_vista.py — vista aproximada (Pillow) de un bloque del estilo «Kinetic»: la pila ya armada, dibujada sin pasar por Resolve.
"""
Sirve para revisar la maqueta de los bloques (qué elemento lleva cada palabra, dónde cae, si se solapan o no caben) en un segundo, sin renderizar en
Resolve, y para las miniaturas del pack en «Estilos». NO es el render real: no tiene las animaciones ni el degradado fino ni las sombras de Fusion.
    dibujar_cue(cue, ancho=1080, alto=1920, fondo=(40, 40, 46) | PIL.Image) -> PIL.Image
"""
from PIL import Image, ImageDraw, ImageFilter

import kinetic_captions as KC

import kinetic_paleta as PAL                      # v5.5.13: los colores del Tema 1 (neón), los mismos del pack


def _colores(k):
    """(abajo, arriba) del relleno del elemento `k`."""
    var = k.split()[-1]
    g = None
    if k.startswith('k hero'):
        g = PAL.GRADIENTES.get(var)
    elif k.startswith('k serif'):
        g = PAL.GRADIENTES['serif']
    elif k.startswith('k script'):
        g = PAL.GUION.get(var)
    return (g[0][1], g[-1][1]) if g else ((1, 1, 1), (1, 1, 1))


CAJAS = PAL.CINTA
ANILLOS = PAL.ANILLO
LINEAS = PAL.LINEA


def _trazo(puntos, color, fx, fy, grosor):
    xs, ys = [p[0] * fx for p in puntos], [p[1] * fy for p in puntos]
    m = grosor + 4
    im = Image.new('RGBA', (int(max(xs) - min(xs) + 2 * m), int(max(ys) - min(ys) + 2 * m)), (0, 0, 0, 0))
    ImageDraw.Draw(im).line([(x - min(xs) + m, y - min(ys) + m) for x, y in zip(xs, ys)], fill=_rgb(color) + (255,), width=max(2, int(grosor)), joint='curve')
    return im, (-min(xs) + m) - im.width / 2.0, (-min(ys) + m) - im.height / 2.0


def _rgb(c):
    return tuple(int(round(v * 255)) for v in c[:3])


def _texto_img(txt, par, px, abajo, arriba, esp=1.0):
    f = KC._fuente(par, px)
    w = int(f.getlength(txt) * esp) + 8
    h = int(px * 1.5)
    mascara = Image.new('L', (w, h), 0)
    ImageDraw.Draw(mascara).text((4, int(px * 0.1)), txt, font=f, fill=255)
    cuerpo = Image.new('RGBA', (w, h))
    for y in range(h):
        k = 1.0 - min(1.0, max(0.0, (y - px * 0.25) / (px * 0.9)))
        col = tuple(int(abajo[i] * 255 * (1 - k) + arriba[i] * 255 * k) for i in range(3))
        ImageDraw.Draw(cuerpo).line([(0, y), (w, y)], fill=col + (255,))
    cuerpo.putalpha(mascara)
    return cuerpo


def _pegar(lienzo, im, cx, cy, rot=0.0, sombra=0.55):
    if rot:
        im = im.rotate(rot, expand=True, resample=Image.BICUBIC)
    if sombra:
        s = Image.new('RGBA', im.size, (0, 0, 0, 0))
        s.putalpha(im.getchannel('A').point(lambda v: int(v * sombra)))
        s = s.filter(ImageFilter.GaussianBlur(5))
        lienzo.alpha_composite(s, (int(cx - im.width / 2), int(cy - im.height / 2 + 4)))
    lienzo.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))


def dibujar_cue(cue, ancho=1080, alto=1920, fondo=(40, 40, 46)):
    lienzo = fondo.convert('RGBA').resize((ancho, alto)) if hasattr(fondo, 'convert') else Image.new('RGBA', (ancho, alto), tuple(fondo) + (255,))
    escala = ancho / 1080.0
    for r in cue['runs']:
        k = r['k']
        e = KC._espec(k)
        cx, cy = r['x'] * ancho, r['y'] * alto
        if e['tipo'] == 'texto':
            px = r['size'] * KC.K_PX * escala
            ab, ar = _colores(k)
            im = _texto_img(r['texto'], e['par'], px, ab, ar, e['esp'])
            _pegar(lienzo, im, cx, cy + px * 0.12, r.get('rot', 0.0))
        elif e['tipo'] == 'cinta':
            px = r['size'] * KC.K_PX * escala
            caja, tinta = CAJAS[k.split()[-1]]
            alto_k, pad_k = e['caja']
            cap = px * KC.CAP[e['par'][0]]
            txt = r['texto']
            f = KC._fuente(e['par'], px)
            tw = f.getlength(txt) * e['esp'] * KC.TINTA
            w, h = int(tw + 2 * cap * pad_k), int(cap * alto_k)
            im = Image.new('RGBA', (w + 8, h + 8), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            d.rounded_rectangle((4, 4, 4 + w, 4 + h), radius=max(2, int(h * 0.08)), fill=_rgb(caja) + (255,))
            d.text((4 + w / 2, 4 + h / 2 + px * 0.02), txt, font=f, fill=_rgb(tinta) + (255,), anchor='mm')
            _pegar(lienzo, im, cx, cy, r.get('rot', 0.0), 0.4)
        elif e['tipo'] == 'trazo' or (e['tipo'] == 'linea' and e.get('curva')):        # v5.5.13: trazos a mano del neón
            if e['tipo'] == 'trazo':
                im, ox, oy = _trazo(PAL.puntos_circulo(lazo='lazo' in k), ANILLOS.get(k.split()[-1], PAL.LIMA), ancho * r['zx'], ancho * r['zy'],
                                    PAL.TRAZO_GROSOR * ancho * (r['zx'] + r['zy']) / 2)
            else:
                im, ox, oy = _trazo(PAL.puntos_subrayado(), LINEAS.get(k.split()[-1], PAL.LIMA), ancho * r['zx'], ancho * r['zy'], PAL.TRAZO_GROSOR * ancho * r['zx'])
            _pegar(lienzo, im, cx - ox, cy - oy, 0.0, 0)
        elif e['tipo'] == 'anillo':
            nw, nh = KC.AFINADO['nominal_anillo']
            w, h = int(nw * ancho * r['zx']), int(nh * ancho * r['zy'])
            im = Image.new('RGBA', (w + 20, h + 20), (0, 0, 0, 0))
            ImageDraw.Draw(im).ellipse((10, 10, 10 + w, 10 + h), outline=_rgb(ANILLOS.get(k.split()[-1], (1, 0.5, 0.1))) + (255,), width=max(3, int(0.012 * ancho * min(r['zx'], r['zy']))))
            _pegar(lienzo, im, cx, cy, r.get('rot', 0.0), 0)
        elif e['tipo'] == 'linea':
            nw, nh = KC.AFINADO['nominal_linea']
            w, h = int(nw * ancho * r['zx']), max(4, int(nh * ancho * r['zy']))
            im = Image.new('RGBA', (w + 4, h + 4), (0, 0, 0, 0))
            ImageDraw.Draw(im).rounded_rectangle((2, 2, 2 + w, 2 + h), radius=h // 2, fill=_rgb(LINEAS.get(k.split()[-1], (1, 0.9, 0.05))) + (255,))
            _pegar(lienzo, im, cx, cy, r.get('rot', 0.0), 0.3)
    return lienzo.convert('RGB')
