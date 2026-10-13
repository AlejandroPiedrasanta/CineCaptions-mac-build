# CineCaptions · By Cinema Productions
# 1_codigo/edicion_pro_persona.py — Edición PRO: dónde está la persona (IA local) para el Magic Mask de Resolve, y su recorte si no hay Magic Mask.
"""
Para que un titular quede DETRÁS de quien habla, Resolve tiene que recortar a la persona en una pista de encima. Dos caminos:

  * Magic Mask (Resolve Studio): la herramienta MagicMask de Fusion necesita puntos sobre la persona; la API no los pone (CreateMagicMask
    solo RASTREA una máscara que ya tiene puntos). Aquí se detecta a cada persona con IA local en el fotograma de referencia y se le dan
    tres puntos (cabeza, pecho, cuerpo). colocar_pro.py escribe esos puntos en la composición y lanza el rastreo.
  * Sin Magic Mask (Resolve Free, o si falla): el recorte entero con IA local, a ProRes 4444 con alfa (solo los segundos que hacen falta).

El modelo es MODNet (Apache-2.0, 2_recursos/edicion_pro/modelos/modnet.onnx, ~25 MB) con onnxruntime (ya va con el programa).
Coordenadas: fracciones del cuadro con el origen ARRIBA a la izquierda (Fusion las quiere con el origen abajo: puntos_fusion()).

    personas(video, t)                       -> {'personas': [{'bbox', 'puntos', 'area'}], 'arriba', 'abajo', 'izq', 'der'} | None
    puntos_fusion(det)                       -> [(x, y)] para MagicMaskStrokes.PosStrokes
    recorte_prores(video, t0, t1, destino)   -> Path del .mov (ProRes 4444, alfa recto) | None
"""
from __future__ import annotations

import threading
from pathlib import Path

import numpy as np

ALTO_MODELO = 512
_SESION = {'s': None, 'entrada': None}
_LOCK = threading.Lock()


def ruta_modelo() -> Path | None:
    """El modelo que viaja con el programa; si faltara, el que se bajó una vez a la caché."""
    try:
        from sfx_rules import base_recursos
        r = Path(base_recursos()) / 'edicion_pro' / 'modelos' / 'modnet.onnx'
    except Exception:
        r = Path(__file__).resolve().parent.parent / '2_recursos' / 'edicion_pro' / 'modelos' / 'modnet.onnx'
    if r.exists():
        return r
    cache = Path.home() / 'DaVinciSubtitles' / 'edicion_pro' / 'modelos' / 'modnet.onnx'
    if cache.exists():
        return cache
    try:                                     # último recurso: el mismo modelo desde Hugging Face (Xenova/modnet, Apache-2.0)
        from huggingface_hub import hf_hub_download
        bajado = Path(hf_hub_download('Xenova/modnet', 'onnx/model.onnx'))
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(bajado.read_bytes())
        return cache
    except Exception:
        return None


def disponible() -> bool:
    try:
        import onnxruntime  # noqa: F401
        import av  # noqa: F401
    except Exception:
        return False
    return ruta_modelo() is not None


def _sesion():
    with _LOCK:
        if _SESION['s'] is None:
            import onnxruntime as ort
            ruta = ruta_modelo()
            if ruta is None:
                raise RuntimeError('falta el modelo de recorte (modnet.onnx)')
            op = ort.SessionOptions()
            op.log_severity_level = 3
            preferidos = [p for p in ('CUDAExecutionProvider', 'DmlExecutionProvider', 'CoreMLExecutionProvider') if p in ort.get_available_providers()]
            s = ort.InferenceSession(str(ruta), sess_options=op, providers=preferidos + ['CPUExecutionProvider'])
            _SESION['s'], _SESION['entrada'] = s, s.get_inputs()[0].name
        return _SESION['s'], _SESION['entrada']


def mate(rgb: np.ndarray) -> np.ndarray:
    """La silueta (0..1) de las personas de una imagen RGB uint8, a ALTO_MODELO px de alto."""
    from PIL import Image
    s, nombre = _sesion()
    h, w = rgb.shape[:2]
    rw = max(32, int(round(w * ALTO_MODELO / h / 32.0)) * 32)
    x = np.asarray(Image.fromarray(rgb).resize((rw, ALTO_MODELO), Image.BILINEAR), dtype=np.float32)
    x = ((x / 255.0 - 0.5) / 0.5).transpose(2, 0, 1)[None]
    return np.clip(s.run(None, {nombre: x})[0][0, 0], 0.0, 1.0)


def fotograma(video, t):
    """El fotograma del video en el segundo t (RGB uint8) o None."""
    import av
    try:
        with av.open(str(video)) as c:
            vs = c.streams.video[0]
            vs.thread_type = 'AUTO'
            tb = float(vs.time_base)
            c.seek(max(0, int((t - 0.5) / tb)), stream=vs, backward=True, any_frame=False)
            ultimo = None
            for f in c.decode(vs):
                ts = float(f.pts * tb) if f.pts is not None else 0.0
                ultimo = f
                if ts >= t - 0.5 / float(vs.average_rate or 30):
                    break
            return ultimo.to_ndarray(format='rgb24') if ultimo is not None else None
    except Exception:
        return None


# ------------------------------------------------------------------------------------------------ máscaras binarias (sin scipy ni cv2)
def _dilatar(m):
    d = m.copy()
    d[1:, :] |= m[:-1, :]
    d[:-1, :] |= m[1:, :]
    d[:, 1:] |= m[:, :-1]
    d[:, :-1] |= m[:, 1:]
    return d


def _inundar(semilla, dentro, maximo=4000):
    """Lo alcanzable desde `semilla` sin salir de `dentro` (reconstrucción geodésica)."""
    r = semilla & dentro
    for _ in range(maximo):
        n = _dilatar(r) & dentro
        if n.sum() == r.sum():
            return n
        r = n
    return r


def rellenar_huecos(m):
    """Cierra los agujeros de la silueta (una cara que el modelo dejó medio transparente)."""
    fuera = ~m
    borde = np.zeros_like(m)
    borde[0, :] = borde[-1, :] = True
    borde[:, 0] = borde[:, -1] = True
    alcanzable = _inundar(borde & fuera, fuera)
    return m | (fuera & ~alcanzable)


def componentes(m, minimo):
    """Las manchas separadas de una máscara (las más grandes primero), cada una como máscara booleana."""
    resto = m.copy()
    out = []
    while resto.any() and len(out) < 8:
        y, x = np.unravel_index(np.argmax(resto), resto.shape)
        semilla = np.zeros_like(resto)
        semilla[y, x] = True
        c = _inundar(semilla, resto)
        resto &= ~c
        if c.sum() >= minimo:
            out.append(c)
    out.sort(key=lambda c: -int(c.sum()))
    return out


def personas(video, t, max_personas=4):
    """Las personas del fotograma t: caja, área y tres puntos (cabeza, pecho, cuerpo) en fracciones del cuadro (origen arriba)."""
    img = fotograma(video, t)
    if img is None:
        return None
    a = mate(img)
    h, w = a.shape
    # rejilla pequeña: las cuentas de manchas son rápidas y no hacen falta más detalles para poner puntos
    k = max(1, h // 128)
    ak = a[::k, ::k]
    m = rellenar_huecos(ak > 0.5)
    gh, gw = m.shape
    salida = []
    for c in componentes(m, minimo=int(0.015 * gh * gw)):
        ys, xs = np.nonzero(c)
        y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
        # una persona de verdad: el modelo está seguro (≥ 0,95), ocupa algo (≥ 3 %) y es alta (≥ 20 % del cuadro); en los planos
        # de B-roll el modelo a veces marca una casa o un mueble con 0,89-0,94 y 2-3 %: eso no es nadie
        if float(ak[c].mean()) < 0.95 or c.sum() < 0.03 * gh * gw or (y1 - y0 + 1) < 0.2 * gh:
            continue
        if len(salida) >= max_personas:
            break
        puntos = []
        for f in (0.12, 0.35, 0.6):
            yy = int(round(y0 + f * (y1 - y0)))
            banda = c[max(0, yy - 1):yy + 2]
            cols = np.nonzero(banda.any(axis=0))[0]
            if len(cols) < 2:
                continue
            cx = cols.mean()
            col = cols[np.argmin(np.abs(cols - cx))]             # un píxel que SÍ es de la persona, el más cercano al centro
            puntos.append((round(float(col + 0.5) / gw, 5), round(float(yy + 0.5) / gh, 5)))
        # la cabeza: de la coronilla hacia abajo el ancho crece y se estrecha en el cuello (o salta en los hombros si el pelo lo tapa)
        anchos = c[y0:y1 + 1].sum(axis=1)
        maxw, filas = 0, None
        for r, wr in enumerate(anchos[:max(4, int(0.45 * (y1 - y0 + 1)))]):
            if r >= 3 and (wr < 0.85 * maxw or wr > 1.6 * maxw):
                filas = r
                break
            maxw = max(maxw, int(wr))
        frente = int(anchos[min(len(anchos) - 1, max(2, int(0.06 * (y1 - y0 + 1))))])
        estimada = 1.35 * frente                                       # alto ≈ 1,35 × el ancho a la altura de la frente (celdas cuadradas)
        cab_alto = (filas if filas and filas <= 1.6 * estimada else estimada) / gh
        if puntos:
            salida.append({'bbox': (round(float(x0) / gw, 4), round(float(y0) / gh, 4), round(float(x1 + 1) / gw, 4), round(float(y1 + 1) / gh, 4)),
                           'area': round(float(c.sum()) / (gh * gw), 4), 'puntos': puntos,
                           'cabeza': {'alto': round(float(cab_alto), 4), 'ancho': round(float(frente) / gw, 4)}})
    if not salida:
        return {'personas': [], 'arriba': None}
    return {'personas': salida, 'arriba': min(p['bbox'][1] for p in salida), 'abajo': max(p['bbox'][3] for p in salida),
            'izq': min(p['bbox'][0] for p in salida), 'der': max(p['bbox'][2] for p in salida)}


def refinar_alfa(a, ancho, alto):
    """El alfa del modelo (a ALTO_MODELO px) al tamaño final con el borde pulido (v5.4.52): escalado bicúbico (sin escalones), una curva suave
    que quita el halo gris de fuera y los huecos claros de dentro, y menos de un píxel de desenfoque en el borde (pelo y hombros). uint8."""
    from PIL import Image, ImageFilter
    img = Image.fromarray((np.clip(a, 0.0, 1.0) * 255).astype(np.uint8), 'L').resize((int(ancho), int(alto)), Image.BICUBIC)
    x = np.clip((np.asarray(img).astype(np.float32) / 255.0 - 0.12) / 0.76, 0.0, 1.0)
    x = x * x * (3.0 - 2.0 * x)
    img = Image.fromarray((x * 255).astype(np.uint8), 'L').filter(ImageFilter.GaussianBlur(max(0.6, int(ancho) / 1800.0)))
    return np.asarray(img)


def puntos_fusion(det):
    """Los puntos para PosStrokes del MagicMask de Fusion (y con el origen ABAJO)."""
    return [(x, round(1.0 - y, 5)) for p in (det or {}).get('personas') or [] for (x, y) in p['puntos']]


def recorte_prores(video, t0, t1, destino, al_progreso=None, lado_max=1920):
    """La persona recortada de t0 a t1 (segundos del ARCHIVO) como ProRes 4444 con alfa recto. Devuelve la ruta o None.
    Se codifica a la resolución del archivo (con el lado largo como mucho `lado_max`): Resolve lo encaja igual que el clip de V1."""
    import av
    from PIL import Image
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix('.tmp.mov')
    try:
        with av.open(str(video)) as c:
            vs = c.streams.video[0]
            vs.thread_type = 'AUTO'
            tb = float(vs.time_base)
            fps = vs.average_rate or 30
            W, H = vs.codec_context.width, vs.codec_context.height
            esc = min(1.0, lado_max / max(W, H))
            ow, oh = int(W * esc) // 2 * 2, int(H * esc) // 2 * 2
            with av.open(str(tmp), 'w') as o:
                os_ = o.add_stream('prores_ks', rate=fps)
                os_.width, os_.height, os_.pix_fmt = ow, oh, 'yuva444p10le'
                os_.options = {'profile': '4', 'vendor': 'apl0', 'qscale': '9'}
                c.seek(max(0, int((t0 - 0.5) / tb)), stream=vs, backward=True, any_frame=False)
                previo, n, total = None, 0, max(1, int((t1 - t0) * float(fps)))
                for f in c.decode(vs):
                    ts = float(f.pts * tb) if f.pts is not None else 0.0
                    if ts < t0 - 0.5 / float(fps):
                        continue
                    if ts >= t1:
                        break
                    rgb = f.to_ndarray(format='rgb24')
                    a = mate(rgb)
                    b = rellenar_huecos(a > 0.5)
                    a = np.maximum(a, b.astype(np.float32) * 0.98)
                    a = a if previo is None else previo * 0.3 + a * 0.7          # suaviza el parpadeo del borde de un fotograma a otro
                    previo = a
                    alfa = refinar_alfa(a, ow, oh)
                    img = rgb if (ow, oh) == (W, H) else np.asarray(Image.fromarray(rgb).resize((ow, oh), Image.BILINEAR))
                    fr = av.VideoFrame.from_ndarray(np.dstack([img, alfa]), format='rgba')
                    for pk in os_.encode(fr):
                        o.mux(pk)
                    n += 1
                    if al_progreso and n % 10 == 0:
                        al_progreso(min(1.0, n / total))
                for pk in os_.encode():
                    o.mux(pk)
        if n == 0:
            tmp.unlink(missing_ok=True)
            return None
        tmp.replace(destino)
        return destino
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        raise
