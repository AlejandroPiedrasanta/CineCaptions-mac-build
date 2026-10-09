# CineCaptions · By Cinema Productions
# 1_codigo/vista_previa_fx.py — la vista previa de 3 segundos de la página «Efectos» (v5.4.8): TODO lo que está encendido, sobre fotos de muestra, sin abrir Resolve.
"""
`renderizar(op)` arma un mp4 de 3 s (360×640, 30 fps) con las opciones actuales de la página Efectos:

    0,0 s  intro                0,3 s  iconos del primer pack activo y número «1»        0,6 s  pegatina       0,9 s  subrayado / círculo
    1,4 s  golpe (temblor)      2,0 s  corte entre dos tomas con la transición elegida    todo el rato: zoom lento, ambiente y mi primer efecto propio

El movimiento del video (zoom, temblor, zoom desenfocado, barrido, glitch) es una APROXIMACIÓN en numpy de lo que hace la composición de Fusion (fusion_v1.py); los clips
(intro, luces, iconos, números, pegatinas, énfasis, ambiente, propios) son los mismos que van a Resolve. El resultado se guarda en la caché según las opciones.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import efectos_extra as X
import efectos_visuales as F

ANCHO, ALTO, FPS = 360, 640, 30
TOTAL = 90
CORTE = 60                                     # el corte entre las dos tomas (2,0 s)
FOTOS = ('fondo_03.jpg', 'fondo_07.jpg')


def efecto_v1(ident, base, u, antes):
    """Una aproximación en numpy de lo que hace la comp de Fusion (fusion_v1.py) en un fotograma: `u` en [0, 1] = cuánto efecto (1 = el corte), `antes` = aún no se cortó."""
    import numpy as np
    from PIL import Image
    h, w = base.shape[:2]
    im = Image.fromarray(base)
    if ident == 'zoom_blur':
        acum = np.zeros((h, w, 3), np.float32)
        pasos = 9
        for k in range(pasos):
            z = 1.0 + 0.16 * u * k / (pasos - 1)
            r = im.resize((int(w * z), int(h * z)), Image.Resampling.BILINEAR)
            x0, y0 = (r.width - w) // 2, (r.height - h) // 2
            acum += np.asarray(r.crop((x0, y0, x0 + w, y0 + h)), np.float32)
        return (acum / pasos).astype(np.uint8)
    if ident == 'whip':
        desp = int((0.30 if antes else -0.30) * w * u)
        acum = np.zeros((h, w, 3), np.float32)
        pasos = 9
        for k in range(pasos):
            acum += np.roll(base, desp + int((k - pasos // 2) * 0.012 * w * u), axis=1).astype(np.float32)
        return (acum / pasos).astype(np.uint8)
    if ident == 'glitch':
        d = int(0.028 * w * u * (1 if (int(u * 97) % 2) else -1))
        salida = base.copy()
        salida[:, :, 0] = np.roll(base[:, :, 0], -d, axis=1)
        salida[:, :, 2] = np.roll(base[:, :, 2], d, axis=1)
        return np.roll(salida, int(0.04 * w * u * (1 if (int(u * 53) % 2) else -1)), axis=1)
    return base


def _foto(k):
    from PIL import Image
    ruta = F.carpeta_efectos().parent / 'fondos_estilos' / FOTOS[k % len(FOTOS)]
    f = Image.open(ruta).convert('RGB')
    esc = max(ANCHO / f.width, ALTO / f.height)
    f = f.resize((int(f.width * esc + 1), int(f.height * esc + 1)), Image.Resampling.LANCZOS)
    return f.crop(((f.width - ANCHO) // 2, (f.height - ALTO) // 2, (f.width - ANCHO) // 2 + ANCHO, (f.height - ALTO) // 2 + ALTO))


def _cuadros_de_video(ruta, n_max=200):
    """Los fotogramas de un mp4 de efecto (negro de fondo), a ANCHO×ALTO, como arrays RGB uint8."""
    import av
    import numpy as np
    salida = []
    try:
        with av.open(str(ruta)) as c:
            for k, fr in enumerate(c.decode(video=0)):
                if k >= n_max:
                    break
                salida.append(fr.reformat(width=ANCHO, height=ALTO, format='rgb24').to_ndarray())
    except Exception:
        pass
    return salida


def _screen(base, capa, fuerza=1.0):
    import numpy as np
    a = base.astype(np.float32) / 255.0
    b = capa.astype(np.float32) / 255.0 * fuerza
    return (255.0 * (1.0 - (1.0 - a) * (1.0 - b))).astype(np.uint8)


def _componer(base, secuencia, k):
    """Pone el fotograma k (1…n) de una secuencia de PNG con alpha encima de `base` (array RGB)."""
    from PIL import Image
    import numpy as np
    if not secuencia or not (1 <= k <= secuencia['n']):
        return base
    try:
        cuadro = Image.open(secuencia['patron'] % k).convert('RGBA')
    except Exception:
        return base
    fondo = Image.fromarray(base).convert('RGBA')
    fondo.alpha_composite(cuadro)
    return np.asarray(fondo.convert('RGB'))


def _huella(op):
    claves = ('fx_intro', 'fx_cortes', 'fx_iconos_activo', 'fx_iconos', 'fx_zoom', 'fx_temblor', 'fx_intensidad', 'fx_numeros', 'fx_pegatinas', 'fx_pegatinas_palabras', 'fx_enfasis',
              'fx_enfasis_altura', 'fx_overlay', 'fx_overlay_fuerza', 'fx_propios')
    datos = {k: op.get(k) for k in claves}
    return hashlib.md5(json.dumps(datos, sort_keys=True, default=str).encode('utf-8')).hexdigest()[:10]


def ruta_vista(op=None):
    op = op or F.opciones_guardadas()
    return F.CACHE / f'vista_{_huella(op)}_{F.REVISION}' / 'vista.mp4'


def renderizar(op=None, al_estado=None):
    """El mp4 de la vista previa con las opciones `op` (o las guardadas). Devuelve la ruta (se reutiliza si ya está hecha) o None."""
    import numpy as np
    op = dict(op or F.opciones_guardadas())
    destino = ruta_vista(op)
    if destino.is_file() and destino.stat().st_size > 5000:
        return str(destino)
    delta = F.DESPLAZA.get(op.get('fx_intensidad', 'normal'), 0)
    A, B = np.asarray(_foto(0)), np.asarray(_foto(1))
    evitar = [X.zona_captions(ANCHO, ALTO)]
    zoom = F.nivel_de(op.get('fx_zoom'), delta)
    temblor = F.nivel_de(op.get('fx_temblor'), delta)
    trans = op.get('fx_cortes') or ''
    # --- los clips
    intro = _cuadros_de_video(F._clip('intro', op['fx_intro'], 'v')) if op.get('fx_intro') and F._clip('intro', op['fx_intro'], 'v') else []
    luz = _cuadros_de_video(F._clip('corte', trans, 'v')) if trans and trans not in F.TRANSICIONES_V1 and F._clip('corte', trans, 'v') else []
    packs = [p for p in (op.get('fx_iconos') or []) if p in {x[0] for x in F.PACKS_ICONOS}] if op.get('fx_iconos_activo', True) else []
    iconos = F.secuencia_iconos(packs[0], ANCHO, ALTO, 0, evitar=evitar) if packs else None
    numero = X.secuencia_numero(1, ANCHO, ALTO, evitar, 0) if op.get('fx_numeros') else None
    pegatina = None
    if op.get('fx_pegatinas'):
        eid = next((v for v in (op.get('fx_pegatinas_palabras') or {}).values() if v), None) or 'money_bag'
        pegatina = X.secuencia_pegatina(eid, ANCHO, ALTO, evitar, 0) or X.secuencia_pegatina('money_bag', ANCHO, ALTO, evitar, 0)
    enfasis = X.secuencia_enfasis(op['fx_enfasis'], ANCHO, ALTO, op.get('fx_enfasis_altura', 'centro')) if op.get('fx_enfasis') in {e[0] for e in X.ENFASIS} else None
    ambiente = _cuadros_de_video(X.clip_overlay(op['fx_overlay'], ANCHO, ALTO)) if op.get('fx_overlay') in {o[0] for o in X.OVERLAYS} else []
    fuerza = max(0.1, min(1.0, float(op.get('fx_overlay_fuerza', 0.45)) * (1.0 + 0.35 * delta)))
    propio_sec, propio_vid, propio_modo = None, [], 'screen'
    for e in op.get('fx_propios') or []:
        if isinstance(e, dict) and e.get('activo', True) is not False and e.get('uso') in ('intro', 'continuo'):
            r = X.preparar_propio(e, ANCHO, ALTO)
            if r and r.get('archivo'):
                propio_vid = _cuadros_de_video(r['archivo'])
            elif r and r.get('secuencia'):
                propio_sec = r['secuencia']
            propio_modo = e.get('modo') or 'screen'
            break
    ZOOM = {'suave': 0.06, 'normal': 0.10, 'fuerte': 0.18}
    TEMB = {'suave': (0.006, 0.020), 'normal': (0.011, 0.035), 'fuerte': (0.018, 0.055)}
    medio = 5

    def fotogramas():
        for f in range(TOTAL):
            t = f / float(FPS)
            base = A if f < CORTE else B
            im_zoom = 1.0 + (ZOOM[zoom] * t / 3.0 if zoom else 0.0)
            dx = dy = 0
            if temblor:
                desp, pico = TEMB[temblor]
                env = max(0.0, 1.0 - (t - 1.4) / 0.36) * (1.0 if t >= 1.4 else 0.0)
                im_zoom *= 1.0 + pico * env
                dx, dy = int(desp * env * math.sin(f * 7.3) * ANCHO), int(desp * 0.8 * env * math.sin(f * 5.9 + 1.7) * ALTO)
            if im_zoom > 1.0005 or dx or dy:
                from PIL import Image
                r = Image.fromarray(base).resize((int(ANCHO * im_zoom), int(ALTO * im_zoom)), Image.Resampling.BILINEAR)
                x0, y0 = (r.width - ANCHO) // 2 - dx, (r.height - ALTO) // 2 - dy
                base = np.asarray(r.crop((x0, y0, x0 + ANCHO, y0 + ALTO)))
            if trans in F.TRANSICIONES_V1:
                u = max(0.0, 1.0 - abs(f - CORTE) / medio)
                if u > 0:
                    base = efecto_v1(trans, np.ascontiguousarray(base), u, f < CORTE)
            if intro and f < len(intro):
                base = _screen(base, intro[f])
            if luz:
                k = f - (CORTE - len(luz) // 2)
                if 0 <= k < len(luz):
                    base = _screen(base, luz[k])
            if ambiente:
                base = _screen(base, ambiente[f % len(ambiente)], fuerza)
            if propio_vid and f < len(propio_vid):
                base = _screen(base, propio_vid[f]) if propio_modo != 'normal' else base
            base = _componer(base, propio_sec, f + 1) if propio_sec else base
            base = _componer(base, iconos, f - 9 + 1) if iconos else base
            base = _componer(base, numero, f - 9 + 1) if numero else base
            base = _componer(base, pegatina, f - 18 + 1) if pegatina else base
            base = _componer(base, enfasis, f - 27 + 1) if enfasis else base
            yield np.ascontiguousarray(base)
    try:
        return X._codificar_video(destino, fotogramas(), ANCHO, ALTO, crf=20)
    except Exception:
        return None
