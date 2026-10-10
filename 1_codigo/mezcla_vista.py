# CineCaptions · By Cinema Productions
# 1_codigo/mezcla_vista.py — las vistas aproximadas (Pillow) de los looks de los TRES temas para «Crea tu estilo»: cada look se ve sobre una foto de muestra, dibujado con el plan REAL de su tema.
"""
mezcla_vista.py  (v5.4.30)
--------------------------
Sin Resolve ni Qt (solo Pillow, así se puede preparar en un hilo): para cada look del catálogo de mezcla_planificador se planifica una frase de muestra con el planificador de su tema
(el mismo que usa GO), se elige el bloque que de verdad enseña ese look (la palabra héroe, la palabra grande, el efecto) y se dibuja con la geometría y las tipografías reales sobre una foto.

    vista(id, foto=0, ancho=324)    -> PIL.Image RGB 9:16 con el look sobre la foto
    poster(ids, foto=0, ancho=540)  -> PIL.Image RGB 9:16 con varios looks apilados (la tarjeta del pack de mezcla en el slider)

NO es el render de Resolve (sin animaciones, brillos de Luxe ni sombras de Fusion): es la maqueta de lo que cada look hace con la frase.
"""
import random
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

import guion_captions as G
import kinetic_captions as KC
import kinetic_vista as KV
import mezcla_planificador as MP
import viral_captions as VC

ANCHO_BASE, ALTO_BASE = 1080, 1920
CLIPS = 'mezcla'                  # 2_recursos/guia_estilo/mezcla/<id>.mp4: los clips REALES de Resolve de cada look (hacer_vistas_mezcla.py)
FRASE = 'Haz que tus videos se vean increíbles con un estilo que nadie más tiene en tus redes'.split()
_CUES = {}                    # id -> (motor, cue) ya elegido
_FOTOS = {}                   # foto -> PIL.Image 1080x1920 (oscurecida)


# ----------------------------------------------------------------------------------------------------------------------------- la foto y el bloque de muestra
def _carpeta_fotos():
    try:
        import instalador_scripts
        return Path(instalador_scripts.BASE_RECURSOS) / 'fondos_estilos'
    except Exception:
        return Path(__file__).resolve().parent.parent / '2_recursos' / 'fondos_estilos'


def id_a_archivo(look_id):
    """'t1:lima' -> 't1_lima' (un nombre de archivo seguro)."""
    return str(look_id).replace(':', '_').replace(' ', '_')


def ruta_clip(look_id):
    """El clip de 6 s que renderizó Resolve para ese look (entrada, texto y salida, sobre negro), o None si todavía no se hizo."""
    try:
        r = _carpeta_fotos().parent / 'guia_estilo' / CLIPS / (id_a_archivo(look_id) + '.mp4')
        return r if r.is_file() and r.stat().st_size > 1000 else None
    except Exception:
        return None


def _foto(k):
    """La foto de muestra número k (cubre el cuadro 9:16, oscurecida un poco para que el texto claro se lea)."""
    rutas = sorted(_carpeta_fotos().glob('fondo_*.jpg')) if _carpeta_fotos().is_dir() else []
    clave = (k % len(rutas)) if rutas else -1
    if clave not in _FOTOS:
        if rutas:
            im = Image.open(rutas[clave]).convert('RGB')
            esc = max(ANCHO_BASE / im.width, ALTO_BASE / im.height)
            im = im.resize((int(im.width * esc) + 1, int(im.height * esc) + 1), Image.LANCZOS)
            x, y = (im.width - ANCHO_BASE) // 2, (im.height - ALTO_BASE) // 2
            im = im.crop((x, y, x + ANCHO_BASE, y + ALTO_BASE))
        else:
            im = Image.new('RGB', (ANCHO_BASE, ALTO_BASE), (30, 34, 46))
        _FOTOS[clave] = Image.blend(im, Image.new('RGB', im.size, (0, 0, 0)), 0.30)
    return _FOTOS[clave]


def _palabras():
    return [{'word': w, 'start': round(0.1 + i * 0.55, 2), 'end': round(0.1 + i * 0.55 + 0.48, 2)} for i, w in enumerate(FRASE)]


def _interesa(look, motor, cue):
    """¿Este bloque enseña el look? (héroe / cinta / serif para el Tema 1, palabra grande para el Tema 2, negrita o efecto para el Tema 3)."""
    claves = [str(r.get('k') or '') for r in (cue.get('runs') or [])]
    if motor == 'kinetic':
        return any(k.startswith(('k hero', 'k tape', 'k serif', 'k script')) for k in claves)
    if motor == 'guion':
        return any(r.get('rol') == 'main' for r in (cue.get('runs') or []))
    if look.get('efecto'):
        return any(k.startswith(look['efecto']) for k in claves)
    return 'v negrita' in claves and len(claves) >= 4


def _bloque(look_id):
    if look_id in _CUES:
        return _CUES[look_id]
    look = MP.look_de(look_id)
    if look is None:
        return None
    pal = _palabras()
    res = MP.planificar(pal, [look_id], 'es', ANCHO_BASE, ALTO_BASE, fin_video=pal[-1]['end'] + 1.0)
    orden = res.get('orden') or []
    elegido = next(((m, c) for m, c in orden if _interesa(look, m, c)), None)
    if elegido is None and orden:
        elegido = max(orden, key=lambda mc: len(mc[1].get('runs') or []))
    _CUES[look_id] = elegido
    return elegido


# ----------------------------------------------------------------------------------------------------------------------------- dibujo
def _rgb(h, por_defecto=(255, 255, 255)):
    try:
        h = str(h or '').lstrip('#')
        if len(h) == 6:
            return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        pass
    return por_defecto


def _capa(ancho, alto):
    return Image.new('RGBA', (ancho, alto), (0, 0, 0, 0))


def _texto_centrado(capa, centro, texto, fuente, color, relleno=255):
    ImageDraw.Draw(capa).text(centro, texto, font=fuente, fill=tuple(color) + (relleno,), anchor='mm')


def _componer(lienzo, sombra, brillo, texto):
    if sombra is not None:
        lienzo.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(max(2, lienzo.width // 180))))
    if brillo is not None:
        lienzo.alpha_composite(brillo.filter(ImageFilter.GaussianBlur(max(2, lienzo.width // 120))))
    lienzo.alpha_composite(texto)


def _dibujar_guion(lienzo, cue, esc):
    ancho, alto = lienzo.size
    var = {}
    try:
        var = G.datos_variantes('Referencia', 'v')
    except Exception:
        var = {}
    texto, sombra, brillo = _capa(ancho, alto), _capa(ancho, alto), _capa(ancho, alto)
    for run in sorted(cue.get('runs') or [], key=lambda r: float(r.get('t') or 0)):
        rol, txt = run.get('rol'), str(run.get('texto') or '')
        if not txt:
            continue
        zoom = float(run.get('zoom') or 1.0)
        n = 0
        color = (255, 255, 255)
        if rol == 'main':
            n = int(run.get('estilo') or cue.get('estilo') or 1)
            v = var.get(n) or {}
            par = tuple(v.get('fuente') or ('Poppins', 'Bold'))
            px = float(v.get('tam') or 0.2) * G.K_PX * zoom * esc
            color = _rgb(v.get('color'))
        else:
            par = G.FINA if rol == 'context' else G.NEGRITA
            px = G.TAM_PEQUENA * G.K_PX * zoom * esc
        f = KC._fuente(par, px)
        if f is None:
            continue
        cx, cy = float(run.get('x', 0.5)) * ancho, float(run.get('y', 0.5)) * alto
        w = f.getlength(txt)
        if rol == 'main' and n in (3, 7, 8):                 # los acentos de Amro: pastilla dorada, tachado rojo y subrayado verde
            d = ImageDraw.Draw(texto)
            if n == 3:
                d.rounded_rectangle((cx - w / 2 - px * 0.28, cy - px * 0.58, cx + w / 2 + px * 0.28, cy + px * 0.50), radius=int(px * 0.18), fill=(242, 168, 29, 255))
            elif n == 7:
                d.rounded_rectangle((cx - w / 2 - px * 0.06, cy - px * 0.04, cx + w / 2 + px * 0.06, cy + px * 0.05), radius=2, fill=(224, 32, 32, 255))
            else:
                d.rounded_rectangle((cx - w / 2, cy + px * 0.40, cx + w / 2, cy + px * 0.49), radius=2, fill=(53, 213, 43, 255))
        ImageDraw.Draw(sombra).text((cx, cy + max(1.0, px * 0.05)), txt, font=f, fill=(0, 0, 0, 150), anchor='mm')
        if rol == 'main' and n in (1, 2, 4, 5):             # el brillo de los macros Luxe
            ImageDraw.Draw(brillo).text((cx, cy), txt, font=f, fill=color + (120,), anchor='mm', stroke_width=max(2, int(px * 0.05)), stroke_fill=color + (120,))
        _texto_centrado(texto, (cx, cy), txt, f, color)
    _componer(lienzo, sombra, brillo, texto)


_COLOR_SHATTER = {'': (92, 200, 255), 'rosa': (255, 79, 163), 'lima': (182, 255, 46), 'oro': (255, 201, 60)}
_COLOR_SELECT = {'': (255, 59, 48), 'azul': (58, 141, 255), 'verde': (53, 208, 127), 'naranja': (255, 138, 43)}
_COLOR_DRAG = {'': (255, 255, 255), 'amarillo': (255, 226, 58), 'cian': (46, 230, 240), 'rosa': (255, 79, 163)}


def _grieta(d, caja, color, esc, semilla):
    """Unas grietas finas que cruzan la palabra (el cristal que se rompe)."""
    x0, y0, x1, y1 = caja
    az = random.Random(semilla)
    for _ in range(3):
        x = az.uniform(x0 + (x1 - x0) * 0.15, x1 - (x1 - x0) * 0.15)
        pts = [(x, y0 - 4 * esc)]
        for k in range(1, 5):
            pts.append((x + az.uniform(-0.07, 0.07) * (x1 - x0), y0 + (y1 - y0) * k / 4))
        d.line(pts, fill=(255, 255, 255, 235), width=max(2, int(3 * esc)))
        d.line([(px + 2 * esc, py + 2 * esc) for px, py in pts], fill=color + (150,), width=max(1, int(2 * esc)))


def _dibujar_viral(lienzo, cue, esc):
    ancho, alto = lienzo.size
    texto, sombra, extra = _capa(ancho, alto), _capa(ancho, alto), _capa(ancho, alto)
    de = ImageDraw.Draw(extra)
    for i, run in enumerate(sorted(cue.get('runs') or [], key=lambda r: float(r.get('t') or 0))):
        clave, txt = str(run.get('k') or ''), str(run.get('texto') or '')
        if not txt:
            continue
        base = VC.base_de(clave)
        variante = clave[len(base):].strip() if clave.startswith(base) else ''
        par, _esp = VC._par(base if base in VC.CLIPS else 'v fina')
        px = float(run.get('size') or 0.09) * VC.K_PX * esc
        f = VC._fuente(par, px)
        if f is None:
            continue
        cx, cy = float(run.get('x', 0.5)) * ancho, float(run.get('y', 0.5)) * alto
        w = f.getlength(txt)
        h = px * VC.CAP.get(par[0], 0.73)
        color = (255, 255, 255)
        if base == 'v shatter':
            color = _COLOR_SHATTER.get(variante, _COLOR_SHATTER[''])
        ImageDraw.Draw(sombra).text((cx, cy + max(1.0, px * 0.04)), txt, font=f, fill=(0, 0, 0, 150), anchor='mm')
        if base == 'v negrita':                                  # cursiva sintética (como el clip del pack)
            capa_t = _capa(ancho, alto)
            _texto_centrado(capa_t, (cx, cy), txt, f, color)
            sesgo = VC.INCLINADA.get('v negrita', 0.21)
            capa_t = capa_t.transform(capa_t.size, Image.AFFINE, (1, sesgo, -sesgo * cy, 0, 1, 0), resample=Image.BICUBIC)
            texto.alpha_composite(capa_t)
            continue
        _texto_centrado(texto, (cx, cy), txt, f, color)
        caja = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
        if base == 'v shatter':
            _grieta(de, caja, color, esc, i + len(txt))
        elif base == 'v select':
            c = _COLOR_SELECT.get(variante, _COLOR_SELECT[''])
            m = h * 0.30
            r = (caja[0] - m, caja[1] - m, caja[2] + m, caja[3] + m)
            de.rectangle(r, fill=c + (40,), outline=c + (255,), width=max(2, int(4 * esc)))
            t = max(5, int(11 * esc))
            for (hx, hy) in ((r[0], r[1]), (r[2], r[1]), (r[0], r[3]), (r[2], r[3])):
                de.rectangle((hx - t, hy - t, hx + t, hy + t), fill=(255, 255, 255, 255), outline=c + (255,), width=max(2, int(3 * esc)))
        elif base == 'v drag':
            c = _COLOR_DRAG.get(variante, _COLOR_DRAG[''])
            de.rectangle((caja[0], caja[1] - h * 0.12, caja[0] + (caja[2] - caja[0]) * 0.62, caja[3] + h * 0.12), fill=c + (90,))
            x, y = caja[0] + (caja[2] - caja[0]) * 0.62, caja[3] + h * 0.12             # el cursor que arrastra
            s = h * 0.55
            flecha = [(x, y), (x, y + s), (x + s * 0.28, y + s * 0.74), (x + s * 0.50, y + s * 1.10), (x + s * 0.68, y + s * 1.00), (x + s * 0.48, y + s * 0.66), (x + s * 0.80, y + s * 0.66)]
            de.polygon(flecha, fill=(255, 255, 255, 255), outline=(0, 0, 0, 255))
    lienzo.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(max(2, ancho // 180))))
    lienzo.alpha_composite(extra)
    lienzo.alpha_composite(texto)


# ----------------------------------------------------------------------------------------------------------------------------- lo que se pide
def _desplazado(cue, dy):
    """El bloque con todo su texto `dy` (fracción del alto) más abajo (para apilar varios looks en un solo cuadro)."""
    if not dy:
        return cue
    c = dict(cue)
    c['runs'] = [dict(r, y=float(r.get('y', 0.5)) + dy) for r in (cue.get('runs') or [])]
    if c.get('caja'):
        c['caja'] = [float(v) + dy for v in c['caja']]
    return c


def _pintar(lienzo, motor, cue, esc, dy=0.0):
    """Dibuja el bloque sobre `lienzo` (RGBA) y devuelve el lienzo (RGBA)."""
    cue = _desplazado(cue, dy)
    if motor == 'kinetic':
        return KV.dibujar_cue(cue, lienzo.width, lienzo.height, fondo=lienzo).convert('RGBA')
    if motor == 'viral':
        _dibujar_viral(lienzo, cue, esc)
    else:
        _dibujar_guion(lienzo, cue, esc)
    return lienzo


def _lienzo(foto, ancho):
    alto = int(round(int(ancho) * 16 / 9))
    return _foto(foto).resize((int(ancho), alto), Image.LANCZOS).convert('RGBA')


def vista(look_id, foto=0, ancho=324):
    """El look sobre una foto de muestra: PIL.Image RGB 9:16 de `ancho` px de ancho (o None si el id no existe)."""
    b = _bloque(look_id)
    if b is None:
        return None
    motor, cue = b
    return _pintar(_lienzo(foto, ancho), motor, cue, int(ancho) / float(ANCHO_BASE)).convert('RGB')


def poster(ids, foto=0, ancho=540):
    """Varios looks apilados en una sola foto 9:16 (la tarjeta del pack de mezcla): hasta 3, repartidos de arriba abajo."""
    lienzo = _lienzo(foto, ancho)
    ids = [i for i in ids][:3]
    esc = int(ancho) / float(ANCHO_BASE)
    for k, i in enumerate(ids):
        b = _bloque(i)
        if b is None:
            continue
        motor, cue = b
        caja = cue.get('caja') or [0.45, 0.70]
        centro = (float(caja[0]) + float(caja[1])) / 2.0
        meta = (k + 1) / (len(ids) + 1.0) * 0.86 + 0.06           # franjas a lo largo del cuadro (sin pegar al borde)
        lienzo = _pintar(lienzo, motor, cue, esc, dy=meta - centro)
    return lienzo.convert('RGB')
