# CineCaptions · By Cinema Productions
# 1_codigo/tipo_vista.py — el bloque del Tema 5 («v tipo») dibujado con Pillow: vistas, GO sin Resolve y la vista de Creativo.
"""
tipo_vista.py  (v5.76)
----------------------
Dibuja un bloque del Tema 5 nuevo (tipo_planificador: el texto codificado de su clip «v tipo») como lo hace su comp de Fusion
(viral_elementos.comp_tipo): la grande sin lo que tapa el contorno de las serif (el «hueco»), bisel con la luz de arriba a la izquierda y sombra
suave debajo. Con `t` (segundos desde el inicio del clip) solo lo ya dicho, como el Write On del clip.

    estados(texto)                          -> los instantes (s) en que aparece algo
    dibujar(texto, ancho, alto, t, color)   -> PIL RGBA del cuadro entero (ancho × alto)
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import tipo_planificador as TP
import viral_captions as VC

HUECO_EM = 0.07                 # lo que el hueco sale de la serif (em de la serif; medido en el render de Resolve: ~0,06-0,08)
BISEL = (0.014, 0.45, 0.30)     # difuminado de la altura (em de la grande), cuánto aclara la luz, cuánto oscurece la sombra (viral_elementos.TIPO_VOLUMEN)
TONO_SOMBRA = np.array([0.10, 0.13, 0.22])
SOMBRA = (0.40, 0.003, 0.012)   # opacidad, bajada (× alto), difuminado (× ancho)


def estados(texto):
    ts = {0.0}
    for linea in TP.decodificar(texto):
        if linea:
            ts.update(t for t, _f in linea['tabla'])
    return sorted(ts)


def _visibles(linea, t):
    txt = linea['texto']
    if t is None:
        return txt
    f = 0.0
    for tt, ff in linea['tabla']:
        if t + 1e-6 >= tt:
            f = ff
    return txt if f >= 1.0 else txt[:int(f * len(txt) + 1e-6)].rstrip()


def dibujar(texto, ancho, alto, t=None, color=(1.0, 1.0, 1.0)):
    lineas = TP.decodificar(texto)
    grande = Image.new('L', (ancho, alto), 0)
    serif = Image.new('L', (ancho, alto), 0)
    hueco = Image.new('L', (ancho, alto), 0)
    em_g = 0.0
    for linea in lineas:
        if not linea:
            continue
        par = linea['par']
        em = linea['size'] * TP.K_PX[par] * ancho / 1080.0
        f = VC._fuente(par, em)
        vis = _visibles(linea, t)
        if f is None or not vis:
            continue
        x = linea['cx'] * ancho - f.getlength(linea['texto']) / 2.0          # (el Text+ centra la línea ENTERA; el Write On no la mueve)
        base = (1.0 - linea['cy']) * alto + TP.CAP[par] * em / 2.0 - TP.DY_EM[par] * em
        if par == TP.GRANDE:
            em_g = max(em_g, em)
            ImageDraw.Draw(grande).text((x, base), vis, font=f, fill=255, anchor='ls')
        else:
            ImageDraw.Draw(serif).text((x, base), vis, font=f, fill=255, anchor='ls')
            ImageDraw.Draw(hueco).text((x, base), vis, font=f, fill=255, anchor='ls', stroke_width=max(1, int(round(HUECO_EM * em))), stroke_fill=255)
    g = np.asarray(grande, np.float32) / 255.0
    g = g * (1.0 - np.asarray(hueco, np.float32) / 255.0)
    a = np.maximum(g, np.asarray(serif, np.float32) / 255.0)
    if a.max() <= 0.0:
        return Image.new('RGBA', (ancho, alto), (0, 0, 0, 0))
    # el bisel: la altura es el alfa difuminado; donde sube hacia abajo a la derecha (borde de arriba a la izquierda) da la luz
    radio = max(1.0, BISEL[0] * (em_g or 0.15 * ancho))
    h = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(radio)), np.float32) / 255.0
    gy, gx = np.gradient(h)
    s = np.clip((gx + gy) * radio * 1.6, -1.0, 1.0)
    luz, sombra = np.clip(s, 0, 1)[..., None], np.clip(-s, 0, 1)[..., None]
    base_c = np.array(color, np.float32)[None, None, :]
    cara = base_c + luz * BISEL[1] * (1.0 - base_c) - sombra * BISEL[2] * (base_c - TONO_SOMBRA[None, None, :])
    cara = np.clip(cara, 0, 1)
    # la sombra suave debajo
    op, baja, difu = SOMBRA
    sa = Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(max(1.0, difu * ancho)))
    sa = np.asarray(sa, np.float32) / 255.0 * op
    dy = int(round(baja * alto))
    if dy:
        sa = np.vstack([np.zeros((dy, ancho), np.float32), sa[:-dy]])
    # cara encima de la sombra (alfa no premultiplicado)
    a_tot = a + sa * (1.0 - a)
    rgb = (cara * a[..., None]) / np.maximum(a_tot, 1e-6)[..., None]
    out = np.dstack([np.clip(rgb * 255.0 + 0.5, 0, 255), np.clip(a_tot * 255.0 + 0.5, 0, 255)]).astype(np.uint8)
    return Image.fromarray(out, 'RGBA')
