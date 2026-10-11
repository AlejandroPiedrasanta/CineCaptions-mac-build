# CineCaptions · By Cinema Productions
# 1_codigo/tema4_vista.py — vista aproximada (Pillow) de un bloque del Tema 4: las palabras ya dichas en su sitio, con el brillo suave. Para comparar con la referencia sin pasar por Resolve.
"""
    dibujar(cue, t, fondo=None, ancho=1080, alto=1920) -> PIL.Image RGB
"""
from PIL import Image, ImageDraw, ImageFilter

import guion_captions as GC
import tema4_planificador as T


def dibujar(cue, t=None, fondo=None, ancho=1080, alto=1920):
    """El bloque en el instante t (solo las palabras que ya entraron; t=None = todas) sobre `fondo` (PIL.Image) o un gris."""
    lienzo = fondo.convert('RGBA').resize((ancho, alto)) if fondo is not None else Image.new('RGBA', (ancho, alto), (70, 76, 84, 255))
    esc = ancho / 1080.0
    texto = Image.new('RGBA', (ancho, alto), (0, 0, 0, 0))
    d = ImageDraw.Draw(texto)
    for r in cue['runs']:
        if t is not None and float(r.get('t', cue['start'])) > t:
            continue
        em = T.EM_BASE * float(r.get('zoom', 1.0)) * esc
        f = GC._fuente(T.FUENTE, em)
        if f is None:
            continue
        cx, cy = float(r['x']) * ancho, float(r['y']) * alto
        # el texto se centra por su caja de tinta: se dibuja letra a letra con el espaciado apretado y se centra el conjunto
        anchos = [f.getlength(ch) * T.ESPACIADO for ch in r['texto']]
        total = sum(anchos)
        x = cx - total / 2.0
        # la línea de base: el centro del texto está CENTRO_CAP em por encima de ella
        base = cy + T.CENTRO_CAP * em
        for ch, a in zip(r['texto'], anchos):
            d.text((x, base), ch, font=f, fill=(255, 255, 255, 255), anchor='ls')
            x += a
    brillo = texto.filter(ImageFilter.GaussianBlur(max(2, 7 * esc)))
    sombra = Image.new('RGBA', texto.size, (0, 0, 0, 0))
    sombra.putalpha(brillo.getchannel('A').point(lambda v: int(v * 0.55)))
    lienzo.alpha_composite(sombra)
    lienzo.alpha_composite(texto)
    return lienzo.convert('RGB')
