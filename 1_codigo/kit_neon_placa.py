# CineCaptions · By Cinema Productions
# 1_codigo/kit_neon_placa.py — v5.5.13: la PLACA de video del Tema 1 neón: el motor/plate.py del kit «TEMA 1» del usuario, portado a Pillow + numpy +
# PyAV (el programa no lleva OpenCV). Mismas cuentas: grade cálido, cámara (medio / cerrado con muelle hacia la cara), deriva lenta por plano,
# asentamiento al entrar cada plano, pantallas divididas (el video encoge con muelle a una tarjeta redondeada sobre el fondo morado), desenfoques
# (bajo la órbita y la tarjeta de ruta), y desenfoque de movimiento de la TRANSFORMACIÓN (5 subfotogramas cuando la cámara se mueve).
"""
La API de Resolve no deja animar el zoom de un clip; por eso, como el kit, se RENDERIZA la placa (un .mp4 del tamaño del timeline, sin audio) y la
Edición PRO la pone encima de V1 (pista PRO-ZOOM, capa 'placa'): el sonido sigue saliendo de V1.

    plan_placa(video, duracion, captions, motions, cortes) -> dict      (lo que el ejemplo escribía a mano en proyecto.json)
    renderizar(video, plan, salida, ancho=1080, alto=1920, fps=None, progreso=None) -> Path | None
"""
import math
from pathlib import Path

import numpy as np

SUB = 5                                   # subfotogramas del desenfoque de movimiento (obturador de 180°)
FONDO_COLORES = {'arriba': '#2C1E4A', 'abajo': '#110C1D', 'brillo': '#FF2DCB'}
GRADE = {'calido': 1.0, 'contraste': 1.05, 'saturacion': 1.06}


def muelle(p, z=0.7, w=7.6):
    if p <= 0:
        return 0.0
    if p >= 1:
        return 1.0
    wd = w * math.sqrt(1 - z * z)
    return 1 - math.exp(-z * w * p) * (math.cos(wd * p) + (z * w / wd) * math.sin(wd * p))


def suave(p):
    p = min(max(p, 0.0), 1.0)
    return p * p * (3 - 2 * p)


def sale(p):
    p = min(max(p, 0.0), 1.0)
    return 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2


def _rgb(c):
    c = c.lstrip('#')
    return np.array([int(c[i:i + 2], 16) for i in (0, 2, 4)], np.float32)


# ------------------------------------------------------------------------------------------------ el plan (lo que el kit escribía a mano)
def _cara(video, t):
    """(x, y) de la cabeza de la persona más grande en t, en fracciones de la fuente; None si no hay nadie."""
    try:
        import edicion_pro_persona as PE
        if not PE.disponible():
            return None
        r = PE.personas(video, t) or {}
        ps = sorted(r.get('personas') or [], key=lambda p: -p.get('area', 0))
        if not ps:
            return None
        x, y = ps[0]['puntos'][0][:2]
        return float(x), float(y)
    except Exception:
        return None


def plan_placa(video, duracion, captions=None, motions=None, cortes=None):
    """Cámara, planos, desenfoques del Tema 1 neón para CUALQUIER video, con las reglas del ejemplo:
    · planos = los cortes del video; cada plano entra con un leve zoom que se asienta y deriva despacio (±5 %, alterno);
    · punch-in con muelle a 1,12–1,15 hacia la cara en la palabra fuerte de uno de cada dos captions (el gancho a 1,15), y vuelta a 1,0 con
      muelle al empezar el siguiente bloque; en los cortes, cambio seco;
    · desenfoque bajo la órbita (22, con rampa) y desenfoque + oscurecido bajo la tarjeta de ruta (14, 0,62, seco)."""
    dur = float(duracion)
    cortes = sorted({round(float(c[0] if isinstance(c, (list, tuple)) else c), 3) for c in (cortes or []) if 0.3 < float(c[0] if isinstance(c, (list, tuple)) else c) < dur - 0.3})
    planos = [0.0] + cortes
    camara = []
    cara_cache = {}

    def cara(t):
        k = round(t, 1)
        if k not in cara_cache:
            cara_cache[k] = _cara(video, t)
        return cara_cache[k] or (0.5, 0.36)

    camara.append([0.0, 1.0, cara(0.5), 'corte'])
    for c in cortes:
        camara.append([c, 1.0, cara(c + 0.3), 'corte'])
    libres = [(m['ini'], m['fin']) for m in (motions or []) if m.get('abajo') or m.get('split') or m['fn'] in ('orbita', 'barrido')]
    for k, e in enumerate(captions or []):
        if k % 2:
            continue
        big = next((it for it in e['a'].get('items') or [] if it['k'] == 'big'), None)
        if not big:
            continue
        t = float(big['t'] if not isinstance(big['t'], list) else big['t'][0]) - 0.06
        fin = float(e['a'].get('tout', t + 1.5))
        if any(a - 0.3 < fin and t < b + 0.3 for a, b in libres) or any(t - 0.2 < c < fin + 0.2 for c in cortes):
            continue
        camara.append([round(t, 3), 1.15 if k == 0 else 1.12, cara(t), 'muelle'])
        camara.append([round(fin + 0.1, 3), 1.0, cara(t), 'muelle'])
    camara.sort(key=lambda x: x[0])
    desenfoques = []
    for m in motions or []:
        if m['fn'] == 'orbita':
            desenfoques.append({'tin': m['a']['tin'], 'tout': m['a']['tout'], 'blur': 22, 'rampa_in': 0.3, 'rampa_out': 0.4})
        elif m['fn'] == 'tarjetaRuta':
            desenfoques.append({'tin': m['a']['tin'], 'tout': m['a']['tout'], 'blur': 14, 'oscuro': 0.62, 'seco': True})
    # pantallas divididas (kit: «dos»): la tarjeta de arriba con el video, centrada en la cara de ese momento; la de abajo es un gráfico (KitNeon)
    tarjetas = []
    for m in motions or []:
        if m.get('split'):
            fx, fy = cara(m['a']['tin'] + 0.4)
            tj = dict(m.get('tarjeta') or {})
            tarjetas.append({'tin': m['a']['tin'], 'tout': m['a']['tout'], 'top': tj.get('top', [40, 200, 1000, 930, 52]),
                             # (kit: la región va CENTRADA en la cara —«dos»: 505 con la cara en 510— y un 4 % más abajo en la de 4; antes +9 %: cortaba lo de arriba)
                             'region_c_frac': [fx, min(0.62, fy + float(tj.get('dy_cara', 0.0)))], 'cara_frac': [fx, fy],
                             'region_w_frac': tj.get('region_w_frac', 1.0),
                             **({'zoom_t': tj['zoom_t'], 'zoom': tj.get('zoom', 1.12)} if tj.get('zoom_t') else {})})
    return {'duracion': dur, 'planos': planos, 'asentar': list(planos), 'deriva': 0.05, 'camara': camara, 'desenfoques': desenfoques,
            'tarjetas': tarjetas, 'fondo': dict(FONDO_COLORES), 'grade': dict(GRADE)}


# ------------------------------------------------------------------------------------------------ el render (plate.py)
class _Placa:
    def __init__(self, plan, sw, sh, W, H):
        self.p, self.SW, self.SH, self.W, self.H = plan, sw, sh, W, H
        self.BASE = max(W / sw, H / sh)
        self.OX = (W - sw * self.BASE) / 2
        self.OY = (H - sh * self.BASE) / 2
        g = plan.get('grade') or GRADE
        k = g.get('calido', 1.0)
        x = np.arange(256) / 255.0
        c = np.clip(0.5 + (x - 0.5) * g.get('contraste', 1.05), 0, 1)
        self.lut = [((v * 255 + 0.5).astype(np.uint8)) for v in (np.clip(c * (1 + 0.035 * k) + 0.012 * k, 0, 1), np.clip(c + 0.006 * k, 0, 1),
                                                                  np.clip(c * (1 - 0.06 * k) + 0.004, 0, 1))]
        self.sat = g.get('saturacion', 1.06)
        f = plan.get('fondo') or FONDO_COLORES
        y = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
        base = _rgb(f['arriba']) * (1 - y) + _rgb(f['abajo']) * y
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        glow = np.exp(-(((xx - W / 2) / (700 * W / 1080)) ** 2 + ((yy - 300 * H / 1920) / (650 * H / 1920)) ** 2))[..., None]
        self.fondo = np.broadcast_to(base, (H, W, 3)) + glow * _rgb(f.get('brillo', '#FFFFFF')) * 0.12
        self.planos = sorted(plan.get('planos') or [0.0])
        self.camara = [(float(k[0]), float(k[1]), (float(k[2][0]) * sw, float(k[2][1]) * sh), k[3]) for k in plan.get('camara') or [[0, 1.0, (0.5, 0.36), 'corte']]]
        self._mascaras = {}
        for cfg in plan.get('tarjetas') or []:                        # (las posiciones del plan, en fracciones de la fuente)
            if cfg.get('region_c_frac') and not cfg.get('region_c'):
                cfg['region_c'] = [cfg['region_c_frac'][0] * sw, cfg['region_c_frac'][1] * sh]
                cfg['region_w'] = sw * float(cfg.get('region_w_frac') or 1.0)
            if cfg.get('cara_frac') and not cfg.get('cara'):
                cfg['cara'] = [cfg['cara_frac'][0] * sw, cfg['cara_frac'][1] * sh]

    def grade(self, img):
        """El grade del kit (curva cálida + contraste por canal y saturación), en Pillow (C): LUT por canal + ImageEnhance.Color (la misma mezcla con
        la luma). Devuelve una imagen RGB de 8 bits."""
        from PIL import ImageEnhance
        if not hasattr(self, '_lut_pil'):
            self._lut_pil = [int(v) for canal in self.lut for v in canal]
        return ImageEnhance.Color(img.convert('RGB').point(self._lut_pil)).enhance(self.sat)

    def _clave(self, t):
        ks = self.camara
        k = max(i for i, kk in enumerate(ks) if t >= kk[0] or i == 0)
        t0, s1, a1, modo = ks[k]
        if modo == 'muelle' and k > 0:
            _, s0, a0, _ = ks[k - 1]
            p = muelle((t - t0) / 0.5, z=0.75, w=8.0)
            return s0 + (s1 - s0) * p, (a0[0] + (a1[0] - a0[0]) * p, a0[1] + (a1[1] - a0[1]) * p)
        return s1, a1

    def camara_en(self, t):
        s, a = self._clave(t)
        idx = max(i for i, p in enumerate(self.planos) if t >= p or i == 0)
        p0 = self.planos[idx]
        p1 = self.planos[idx + 1] if idx + 1 < len(self.planos) else self.p['duracion']
        d = 1.0
        dv = float(self.p.get('deriva', 0.05))
        if dv > 0 and p1 - p0 >= 1.0:
            e = 1 - math.exp(-max(0.0, t - p0) / 6.0)
            d = 1 + dv * e if idx % 2 == 0 else 1 + dv - dv * e
        if any(abs(p0 - x) < 0.02 for x in self.p.get('asentar') or []):
            d *= 1 + 0.05 * (1 - muelle((t - p0) / 0.55, z=0.75, w=8.0))
        return max(1.0, s * d), a

    def _tarjeta_amount(self, cfg, t, din=0.55, dout=0.45):
        if t < cfg['tin'] or t >= cfg['tout'] + dout:
            return 0.0
        a = muelle((t - cfg['tin']) / din, z=0.72, w=7.6)
        if t >= cfg['tout']:
            a *= 1 - sale((t - cfg['tout']) / dout)
        return a

    def estado(self, t):
        e = {'cam': self.camara_en(t), 'blur': 0.0, 'oscuro': 1.0, 'split': None}
        for k, cfg in enumerate(self.p.get('tarjetas') or []):
            a = self._tarjeta_amount(cfg, t)
            if a > 0:
                zoom = 1 + 0.04 * (1 - math.exp(-(t - cfg['tin']) / 5.0))          # deriva dentro de la tarjeta
                if cfg.get('zoom_t') is not None and t >= cfg['zoom_t']:
                    zoom *= 1 + (cfg.get('zoom', 1.12) - 1) * muelle((t - cfg['zoom_t']) / 0.5, z=0.75, w=8.0)
                e['split'] = (k, round(a, 5), round(1 + (zoom - 1) * min(1.0, a), 5))
        for d in self.p.get('desenfoques') or []:
            if d.get('seco'):
                if d['tin'] <= t < d['tout']:
                    e['blur'], e['oscuro'] = d['blur'], d.get('oscuro', 1.0)
            elif d['tin'] <= t < d['tout'] + d.get('rampa_out', 0.4):
                e['blur'] = d['blur'] * suave((t - d['tin']) / d.get('rampa_in', 0.3)) * (1 - suave((t - d['tout']) / d.get('rampa_out', 0.4)))
                e['oscuro'] = 1 - (1 - d.get('oscuro', 1.0)) * (e['blur'] / d['blur'])
        return e

    def _mascara(self, x, y, w, h, r):
        """Máscara redondeada con antialias (2×) y su sombra (la misma, 18 px más abajo y difuminada), en caché."""
        from PIL import Image, ImageDraw, ImageFilter
        clave = tuple(round(v, 1) for v in (x, y, w, h, r))
        hecho = self._mascaras.get(clave)                   # (v5.5.17: se pinta con varios hilos a la vez: leer UNA vez, sin huecos)
        if hecho is None:
            m = Image.new('L', (self.W * 2, self.H * 2), 0)
            ImageDraw.Draw(m).rounded_rectangle([x * 2, y * 2, (x + w) * 2 - 1, (y + h) * 2 - 1], radius=max(0, r * 2), fill=255)
            m = m.resize((self.W, self.H), Image.LANCZOS)
            sombra = Image.new('L', (self.W, self.H), 0)
            sombra.paste(m, (0, int(18 * self.H / 1920)))
            sombra = sombra.resize((self.W // 4, self.H // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(5.5)).resize((self.W, self.H), Image.BILINEAR)
            hecho = (m, np.asarray(sombra, dtype=np.float32)[..., None] / 255.0)
            if len(self._mascaras) > 48:
                self._mascaras.clear()
            self._mascaras[clave] = hecho
        return hecho

    def _tarjeta(self, src, cfg, a, zoom):
        """El video dentro de la tarjeta de arriba de una pantalla dividida (plate.py: _tarjeta), sobre el fondo morado con su sombra."""
        from PIL import Image
        W, H = self.W, self.H
        x1, y1, w1, h1, r1 = [float(v) * (W / 1080 if i in (0, 2, 4) else H / 1920) for i, v in enumerate(cfg['top'])]
        x, y = x1 * a, y1 * a
        w, h = W + (w1 - W) * a, H + (h1 - H) * a
        r = r1 * min(1.0, a)
        c0 = ((W / 2 - self.OX) / self.BASE, (H / 2 - self.OY) / self.BASE)
        rw = float(cfg.get('region_w') or self.SW)
        k = self.BASE + (w1 / rw - self.BASE) * a
        rc = cfg.get('region_c') or [self.SW / 2, self.SH / 2]
        cx, cy = c0[0] + (rc[0] - c0[0]) * a, c0[1] + (rc[1] - c0[1]) * a
        if zoom != 1.0:
            fx, fy = cfg.get('cara') or rc
            cx, cy = fx + (cx - fx) / zoom, fy + (cy - fy) / zoom
            k *= zoom
        hw, hh = (w / 2) / k, (h / 2) / k
        cx = min(max(cx, hw), self.SW - hw) if hw <= self.SW / 2 else self.SW / 2
        cy = min(max(cy, hh), self.SH - hh) if hh <= self.SH / 2 else self.SH / 2
        # solo la zona de la tarjeta (siempre cabe en la fuente: cx/cy ya están dentro), pegada en su sitio
        cw, ch = max(2, int(round(w))), max(2, int(round(h)))
        bx0, by0 = max(0.0, cx - (w / 2) / k), max(0.0, cy - (h / 2) / k)
        bx1, by1 = min(float(self.SW), bx0 + w / k), min(float(self.SH), by0 + h / k)
        lienzo = Image.new('RGB', (W, H))
        lienzo.paste(src.resize((cw, ch), Image.LANCZOS, box=(bx0, by0, bx1, by1)), (int(round(x)), int(round(y))))
        vid = np.asarray(lienzo, dtype=np.float32)
        m, sombra = self._mascara(x, y, w, h, r)
        mm = np.asarray(m, dtype=np.float32)[..., None] / 255.0
        base = self.fondo * (1 - 0.38 * sombra * min(1.0, a))
        return base * (1 - mm) + vid * mm

    def render(self, src, e, como_array=True):
        """La cámara es solo escala + desplazamiento: recorte de la fuente y resize LANCZOS (nítido, sin el unsharp aparte del kit), ~5× más rápido
        que una transformación afín. Pantalla dividida, desenfoque a media resolución y oscurecido, como plate.py."""
        from PIL import Image, ImageFilter
        if e.get('split'):
            k_, a, zoom = e['split']
            out = self._tarjeta(src, self.p['tarjetas'][k_], a, zoom)
            im = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))
        else:
            s, (ax, ay) = e['cam']
            k = self.BASE * s
            qx, qy = ax * self.BASE + self.OX, ay * self.BASE + self.OY
            x0, y0 = ax - qx / k, ay - qy / k                              # el punto de la fuente que cae en (0, 0) del cuadro
            x0 = min(max(0.0, x0), max(0.0, self.SW - self.W / k))         # (dentro de la fuente: sin bordes negros si la cara está al borde)
            y0 = min(max(0.0, y0), max(0.0, self.SH - self.H / k))
            im = src.resize((self.W, self.H), Image.LANCZOS, box=(x0, y0, x0 + self.W / k, y0 + self.H / k))
        if e['blur'] > 0.3:
            pe = im.resize((self.W // 2, self.H // 2), Image.BILINEAR).filter(ImageFilter.GaussianBlur(e['blur'] / 2))
            im = pe.resize((self.W, self.H), Image.BILINEAR)
        if e['oscuro'] < 1:
            im = im.point(lambda v, f=e['oscuro']: int(v * f))
        return np.asarray(im, dtype=np.float32) if como_array else im

    @staticmethod
    def _movimiento(e1, e2):
        if (e1.get('split') is None) != (e2.get('split') is None):
            return 99.0
        if e1.get('split'):
            (n1, a1, z1), (n2, a2, z2) = e1['split'], e2['split']
            return 99.0 if n1 != n2 else abs(a1 - a2) * 1500 + abs(z1 - z2) * 1100
        (s1, c1), (s2, c2) = e1['cam'], e2['cam']
        return abs(s1 - s2) * 1100 + (abs(c1[0] - c2[0]) + abs(c1[1] - c2[1])) * 1.5

    def placa(self, src, t, fps):
        """Un fotograma de salida (imagen RGB). Si la cámara o la tarjeta se mueven en el obturador (180°), media de 5 subfotogramas."""
        from PIL import Image
        sub = [t + (0.5 / fps) * (k + 0.5) / SUB for k in range(SUB)]
        es = [self.estado(x) for x in sub]
        if self._movimiento(es[0], es[-1]) < 0.6:
            return self.render(src, es[SUB // 2], como_array=False)
        acc = np.zeros((self.H, self.W, 3), np.float32)
        for e in es:
            acc += self.render(src, e)
        return Image.fromarray(np.clip(acc / SUB, 0, 255).astype(np.uint8))


def renderizar(video, plan, salida, ancho=1080, alto=1920, fps=None, progreso=None):
    """La placa entera (mismo largo que el video, sin audio) en H.264 de alta calidad. Devuelve la ruta o None."""
    import av
    from PIL import Image
    try:
        ent = av.open(str(video))
        vs = ent.streams.video[0]
        fps = float(fps or vs.average_rate or 30)
        sw, sh = vs.codec_context.width, vs.codec_context.height
        import rotacion_video as RV
        rot = RV.giro(str(video))                                 # (un video de móvil girado: se endereza como en el resto del programa)
        sw, sh = RV.medidas(sw, sh, rot)
        P = _Placa(plan, sw, sh, ancho, alto)
        salida = Path(salida)
        salida.parent.mkdir(parents=True, exist_ok=True)
        tmp = salida.with_suffix('.tmp.mp4')
        sal = av.open(str(tmp), 'w')
        enc = 'libx264'
        try:
            av.codec.Codec(enc, 'w')
        except Exception:
            enc = 'h264_mf'
        from fractions import Fraction
        os_ = sal.add_stream(enc, rate=Fraction(fps).limit_denominator(1001))      # (29,97 = 30000/1001: PyAV quiere una fracción)
        os_.width, os_.height, os_.pix_fmt = ancho, alto, 'yuv420p'
        if enc == 'libx264':
            os_.options = {'crf': '15', 'preset': 'veryfast'}
        dur = float(plan.get('duracion') or 0) or float(ent.duration or 0) / 1e6
        total = max(1, int(round(dur * fps)))
        # v5.5.17: VARIOS fotogramas a la vez (Pillow y numpy sueltan el GIL al escalar, desenfocar y mezclar); se escriben en orden
        import os
        from collections import deque
        from concurrent.futures import ThreadPoolExecutor
        hilos = max(2, min(6, (os.cpu_count() or 4) // 2))
        P.grade(Image.new('RGB', (2, 2)))                                # (la tabla del grade, antes de los hilos)

        def pintar(img, t):
            return av.VideoFrame.from_image(P.placa(P.grade(RV.derecho_img(img, rot)), t, fps))

        def escribir(vf):
            for pk in os_.encode(vf):
                sal.mux(pk)
        n = 0
        cola = deque()
        with ThreadPoolExecutor(hilos, thread_name_prefix='placa') as pool:
            for fr in ent.decode(vs):
                t = n / fps
                if t >= dur:
                    break
                cola.append(pool.submit(pintar, fr.to_image(), t))
                n += 1
                while len(cola) >= 2 * hilos:
                    escribir(cola.popleft().result())
                if progreso and n % 30 == 0:
                    progreso(n / total)
            while cola:
                escribir(cola.popleft().result())
        for pk in os_.encode():
            sal.mux(pk)
        sal.close()
        ent.close()
        tmp.replace(salida)
        return salida
    except Exception:
        try:
            import registro
            registro.excepcion(origen='Tema 1 neón (placa)')
        except Exception:
            pass
        return None


def plan_de_pro(video, plan):
    """El plan de la placa de la Edición PRO (el mismo que usa para_pro: captions ya ajustados a los motions)."""
    import kit_neon_motions as KM
    caps = plan.get('kitneon') or []
    if not plan.get('_neon_ajustado'):
        caps = KM.ajustar_captions(caps, plan.get('kitneon_motions') or [])
    return plan_placa(video, float(plan.get('duracion') or 0), caps, plan.get('kitneon_motions'), plan.get('_cortes'))


def mapa_camara(video, plan, ancho, alto):
    """v5.5.20 («Captions detrás de ti» también en el Tema 1): con la PRO, lo que se ve NO es el video sino la PLACA (zooms hacia la cara,
    deriva, asentamientos). Devuelve una función (detección de la FUENTE en fracciones, t en s) -> la misma detección en fracciones de la
    placa (= del timeline), o None si en ese instante hay pantalla dividida o desenfoque (ahí no va nadie detrás de los captions)."""
    import av
    import rotacion_video as RV
    with av.open(str(video)) as c:
        vs = c.streams.video[0]
        sw, sh = vs.codec_context.width, vs.codec_context.height
    sw, sh = RV.medidas(sw, sh, RV.giro(str(video)))
    P = _Placa(plan_de_pro(video, plan), sw, sh, ancho, alto)

    def mapa(det, t):
        if not det or not det.get('personas'):
            return det
        e = P.estado(float(t))
        if e.get('split') or e['blur'] > 0.3:
            return None
        s, (ax, ay) = e['cam']
        k = P.BASE * s
        qx, qy = ax * P.BASE + P.OX, ay * P.BASE + P.OY
        x0 = min(max(0.0, ax - qx / k), max(0.0, P.SW - P.W / k))       # (las mismas cuentas que _Placa.render)
        y0 = min(max(0.0, ay - qy / k), max(0.0, P.SH - P.H / k))

        def fx(x):
            return (x * P.SW - x0) * k / P.W

        def fy(y):
            return (y * P.SH - y0) * k / P.H
        ps = []
        for q in det['personas']:
            bx0, by0, bx1, by1 = q['bbox']
            n = dict(q, bbox=(fx(bx0), fy(by0), fx(bx1), fy(by1)), puntos=[(fx(x), fy(y)) for x, y in q.get('puntos') or []])
            if q.get('cabeza'):
                n['cabeza'] = {'alto': q['cabeza'].get('alto', 0) * P.SH * k / P.H, 'ancho': q['cabeza'].get('ancho', 0) * P.SW * k / P.W}
            ps.append(n)
        return {'personas': ps, 'arriba': min(q['bbox'][1] for q in ps), 'abajo': max(q['bbox'][3] for q in ps),
                'izq': min(q['bbox'][0] for q in ps), 'der': max(q['bbox'][2] for q in ps)}
    return mapa


def para_pro(video, plan, carpeta, ancho, alto, fps, progreso=None):
    """La placa para la Edición PRO (aplicar): con los captions ya ajustados a los motions; en caché por su plan (re-aplicar no la rehace)."""
    import hashlib
    import json
    pp = plan_de_pro(video, plan)                          # (aplicar ya ajusta los captions al empezar)
    h = hashlib.sha1(json.dumps([str(video), ancho, alto, round(float(fps), 3), pp], sort_keys=True, default=str).encode('utf-8')).hexdigest()[:12]
    sal = Path(carpeta) / f'placa_neon_{h}.mp4'
    if sal.exists() and sal.stat().st_size > 100000:
        return sal
    return renderizar(video, pp, sal, ancho, alto, fps, progreso=progreso)
