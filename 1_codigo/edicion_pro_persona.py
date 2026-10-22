# CineCaptions · By Cinema Productions
# 1_codigo/edicion_pro_persona.py — Edición PRO: dónde está la persona (IA local) para el Magic Mask de Resolve, y su recorte si no hay Magic Mask.
"""
Para que un titular quede DETRÁS de quien habla, Resolve tiene que recortar a la persona en una pista de encima. Dos caminos:

  * Magic Mask (Resolve Studio): la herramienta MagicMask de Fusion necesita puntos sobre la persona; la API no los pone (CreateMagicMask
    solo RASTREA una máscara que ya tiene puntos). Aquí se detecta a cada persona con IA local en el fotograma de referencia y se le dan
    tres puntos (la cara y los dos hombros: v5.27, nunca el centro del pecho, donde suele haber un micrófono). colocar_pro.py escribe esos
    puntos en la composición y lanza el rastreo.
  * Sin Magic Mask (Resolve Free, o si falla): el recorte entero con IA local, a ProRes 4444 con alfa (solo los segundos que hacen falta).

El modelo es MODNet (Apache-2.0, 2_recursos/edicion_pro/modelos/modnet.onnx, ~25 MB) con onnxruntime (ya va con el programa).
Coordenadas: fracciones del cuadro con el origen ARRIBA a la izquierda (Fusion las quiere con el origen abajo: puntos_fusion()).

    personas(video, t)                       -> {'personas': [{'bbox', 'puntos', 'area'}], 'arriba', 'abajo', 'izq', 'der'} | None
    personas_de_imagen(rgb)                  -> lo mismo de una imagen ya leída
    puntos_fusion(det)                       -> [(x, y)] para MagicMaskStrokes.PosStrokes
    recorte_prores(video, t0, t1, destino)   -> Path del .mov (ProRes 4444, alfa recto) | None
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

ALTO_MODELO = 512


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
    try:                                     # modelo de respaldo desde el motor auxiliar Python 3.14
        import motor_compat
        motor_compat.descargar_modnet(cache)
        return cache if cache.is_file() else None
    except Exception:
        return None

def disponible() -> bool:
    try:
        import motor_compat
        import av  # noqa: F401
        return motor_compat.instalado() and ruta_modelo() is not None
    except Exception:
        return False


def mate(rgb: np.ndarray, alto=None) -> np.ndarray:
    """Calcula la silueta en el motor auxiliar Python 3.14."""
    import motor_compat
    ruta = ruta_modelo()
    if ruta is None:
        raise RuntimeError('falta el modelo de recorte (modnet.onnx)')
    return motor_compat.mate(rgb, alto=int(alto or ALTO_MODELO), modelo=ruta)

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
            import rotacion_video as RV
            for f in RV.fotogramas(c, vs):                             # (v5.31: un paquete dañado no corta la lectura)
                ts = float(f.pts * tb) if f.pts is not None else 0.0
                ultimo = f
                if ts >= t - 0.5 / float(vs.average_rate or 30):
                    break
            if ultimo is None:
                return None
            import rotacion_video as RV                                   # v5.5.8: derecho, como lo muestra Resolve (videos del celular)
            return RV.derecho_nd(ultimo.to_ndarray(format='rgb24'), RV.cuartos(ultimo))
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
    """Cierra los agujeros de la silueta (una cara que el modelo dejó medio transparente). (v5.31: el relleno de Pillow va en Python píxel a
    píxel y era 5 veces más lento; a 512 px esto tarda ~30 ms: por eso matte_persona rellena la FORMA, a 512, y no la pasada fina.)"""
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


def _pixel_de(c, yy, x_obj, lado=0, cx=None, min_dx=0.0):
    """(columna, fila) de un píxel de DENTRO de la persona (con sus vecinos de los lados también dentro: nunca su borde) en la fila yy —o una
    o dos más abajo— lo más cerca de x_obj; con `lado` -1/+1, solo a ese lado de cx y al menos a min_dx de él. None si no hay."""
    gh, gw = c.shape
    for fila in (yy, yy + 1, yy + 2):
        if not 0 <= fila < gh:
            continue
        f = c[fila]
        dentro = f.copy()
        dentro[1:-1] = f[1:-1] & f[:-2] & f[2:]
        dentro[0] = dentro[-1] = False
        cols = np.nonzero(dentro)[0]
        if lado and cx is not None:
            cols = cols[(cols - cx) * lado >= min_dx]
        if len(cols):
            return int(cols[np.argmin(np.abs(cols - x_obj))]), fila
    return None


def personas(video, t, max_personas=4):
    """Las personas del fotograma t: caja, área y tres puntos (cara y hombros) en fracciones del cuadro (origen arriba)."""
    img = fotograma(video, t)
    if img is None:
        return None
    return personas_de_imagen(img, max_personas)


def personas_de_imagen(img, max_personas=4):
    """personas() de una imagen RGB ya leída (v5.27: Efectos › «Posición» lee el video de corrido y mira cada fotograma)."""
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
        alto_c = y1 - y0 + 1
        # una persona de verdad: ocupa algo (≥ 3 %) y es alta (≥ 20 % del cuadro); en los planos de B-roll el modelo a veces marca una casa o un
        # mueble con 0,89-0,94 y 2-3 %: eso no es nadie
        if c.sum() < 0.03 * gh * gw or alto_c < 0.2 * gh:
            continue
        # la cabeza: de la coronilla hacia abajo el ancho crece y se estrecha en el cuello (o salta en los hombros si el pelo lo tapa)
        anchos = c[y0:y1 + 1].sum(axis=1)
        maxw, filas = 0, None
        for r, wr in enumerate(anchos[:max(4, int(0.45 * alto_c))]):
            if r >= 3 and (wr < 0.85 * maxw or wr > 1.6 * maxw):
                filas = r
                break
            maxw = max(maxw, int(wr))
        # el modelo, seguro (≥ 0,95). v5.27: una persona de cuerpo entero tiene mucho borde fino (brazos, piernas) y se quedaba en 0,92-0,93
        # (PRUEBAS (1).mp4, de pie en una cocina): con ≥ 0,90 vale si es ALTA (≥ 35 %), grande (≥ 5 %) y tiene cabeza (el cuello estrecha)
        conf = float(ak[c].mean())
        if conf < 0.95 and not (conf >= 0.9 and alto_c >= 0.35 * gh and c.sum() >= 0.05 * gh * gw and filas):
            continue
        if len(salida) >= max_personas:
            break
        frente = int(anchos[min(len(anchos) - 1, max(2, int(0.06 * alto_c)))])
        estimada = 1.35 * frente                                       # alto ≈ 1,35 × el ancho a la altura de la frente (celdas cuadradas)
        cab_f = filas if filas and filas <= 1.6 * estimada else estimada
        cab_alto = cab_f / gh
        # v5.27 (el usuario: «solo humanos, no objetos ni nada raro»): los puntos del Magic Mask van en la CARA y en los dos HOMBROS. Antes iban por
        # el centro del pecho y del cuerpo, donde en un podcast está el micrófono (el modelo lo une a la persona) o en un plano entero las manos con
        # algo: Magic Mask recortaba también ese objeto
        yc = int(round(y0 + 0.45 * cab_f))
        fila_cara = np.nonzero(c[yc])[0] if 0 <= yc < gh else np.array([])
        cx = float(fila_cara.mean()) if len(fila_cara) else float(xs.mean())
        ancho_cab = max(1.0, float(len(fila_cara)))                     # (en la fila de la cara: la capucha o el pelo no la ensanchan)
        puntos = []
        cr = c & (ak > 0.5)                                             # (sin los huecos que rellenar_huecos tapó: entre el brazo y el cuerpo no hay nadie)
        p = _pixel_de(cr, yc, cx)
        if p is not None:
            puntos.append((round(float(p[0] + 0.5) / gw, 5), round(float(p[1] + 0.5) / gh, 5)))
        yh = int(round(y0 + 1.3 * cab_f))
        if yh < y1:
            borde = max(1, int(round(0.03 * gw)))                      # (lo que entra por el borde del cuadro suele ser un brazo de micro o un objeto)
            for lado in (-1, 1):
                p = _pixel_de(cr, yh, cx + lado * 0.75 * ancho_cab, lado=lado, cx=cx, min_dx=0.45 * ancho_cab)
                if p is not None and borde <= p[0] < gw - borde:
                    puntos.append((round(float(p[0] + 0.5) / gw, 5), round(float(p[1] + 0.5) / gh, 5)))
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


ALTO_MATTE = 1024                        # v5.31: el BORDE del recorte con el modelo a 1024 px (a 512 el pelo y las orejas llevaban halo de fondo)
ALTO_FORMA = 512                         # …y la FORMA de la persona a 512 (a 1024 el modelo a veces deja huecos dentro del cuerpo)
VERSION_MATTE = 3
MASCARAS = Path.home() / 'DaVinciSubtitles' / 'mascaras_persona'   # v5.31: los mattes de «detrás de ti», FUERA de la caché (Resolve los usa)
DIAS_MASCARAS = 120


def _limpiar_islas(a, binaria):
    """Fuera las manchas sueltas (un trozo de fondo que el modelo marcó): solo quedan las siluetas de al menos el 15 % de la mayor."""
    h, w = binaria.shape
    k = max(1, h // 128)
    g = binaria[::k, ::k]
    trozos = componentes(g, minimo=max(4, int(0.002 * g.size)))
    if len(trozos) <= 1:
        return a if trozos else a * 0.0
    mayor = int(trozos[0].sum())
    vale = np.zeros_like(g)
    for c in trozos:
        if c.sum() >= 0.15 * mayor:
            vale |= c
    vale = _dilatar(_dilatar(vale))                                    # (un poco de margen: el borde fino de esas siluetas también vale)
    grande = np.repeat(np.repeat(vale, k, axis=0), k, axis=1)[:h, :w]
    return a * grande


def _rellenar_huecos_persona(a):
    """Los agujeros DENTRO de la silueta que de verdad son persona: los que el modelo ya veía a medias (alfa medio ≥ 0,25: una cara medio
    transparente) o una mota (≤ 0,2 % de la persona). NO el fondo que queda encerrado entre las piernas o entre un brazo y el cuerpo
    (PRUEBAS (1): 6,8 % de la persona con alfa 0,03; antes se rellenaba y se veía la cocina entre las piernas)."""
    m = a > 0.5
    huecos = rellenar_huecos(m) & ~m
    if not huecos.any():
        return a
    persona = max(1, int(m.sum()))
    tapar = np.zeros_like(m)
    for c in componentes(huecos, minimo=1):
        if float(a[c].mean()) >= 0.25 or c.sum() <= 0.002 * persona:
            tapar |= c
    return np.maximum(a, tapar.astype(np.float32) * 0.98)


def _caja_persona(forma, h, w, caja=None):
    """La zona de la pasada fina (en la rejilla fina): la persona con margen; con `caja` (la del fotograma anterior), la MISMA mientras la
    persona quepa (el modelo no se reajusta a un tamaño nuevo en cada fotograma); si se sale, una más grande que abarque las dos."""
    ys, xs = np.nonzero(forma > 0.05)
    if not len(ys):
        return caja
    my, mx = int(0.1 * h), int(0.1 * w)
    nueva = (max(0, ys.min() - my), min(h, ys.max() + my + 1), max(0, xs.min() - mx), min(w, xs.max() + mx + 1))
    if caja is not None:
        y0, y1, x0, x1 = caja
        if y0 <= ys.min() and ys.max() < y1 and x0 <= xs.min() and xs.max() < x1:
            return caja
        nueva = (min(y0, nueva[0]), max(y1, nueva[1]), min(x0, nueva[2]), max(x1, nueva[3]))
    return nueva


def matte_persona(rgb, previo=None, estado=None):
    """v5.31 (el usuario: «la máscara perfecta para humanos, sin bugs ni fallas»): la silueta de las personas para el recorte, en DOS pasadas
    del modelo: la FORMA a ALTO_FORMA px (robusta: ni huecos en el cuerpo ni manchas de fondo) y el BORDE a ALTO_MATTE px (pelo, orejas,
    dedos), que solo cuenta en una franja alrededor del contorno de la forma; sin manchas sueltas (_limpiar_islas), sin agujeros dentro (la cara,
    una mano delante) y estable de un fotograma a otro sin dejar estela (se suaviza solo donde casi no cambió). Devuelve el alfa (0..1) a la
    resolución de la pasada fina."""
    from PIL import Image
    forma = mate(rgb, ALTO_FORMA)
    forma = _limpiar_islas(forma, forma > 0.5)
    forma = _rellenar_huecos_persona(forma)                            # (los huecos, en la forma: ~30 ms a 512)
    H0, W0 = rgb.shape[:2]
    h = ALTO_MATTE                                                     # (la rejilla fina: el cuadro entero a ALTO_MATTE px de alto)
    w = max(1, int(round(W0 * h / float(H0))))
    forma = np.asarray(Image.fromarray(forma.astype(np.float32)).resize((w, h), Image.BILINEAR), dtype=np.float32)
    fino = np.zeros((h, w), np.float32)
    estado = estado if estado is not None else {}
    caja = _caja_persona(forma, h, w, estado.get('caja'))
    estado['caja'] = caja
    if caja is not None:
        # la pasada fina SOLO sobre la persona (con margen), a ALTO_MATTE px: el modelo es de retratos y, con la persona más grande, ve más
        # detalle (también una persona pequeña en el cuadro) y tarda menos que el cuadro entero
        y0, y1, x0, x1 = caja
        sy, sx = H0 / float(h), W0 / float(w)
        trozo = rgb[int(y0 * sy):int(np.ceil(y1 * sy)), int(x0 * sx):int(np.ceil(x1 * sx))]
        if trozo.size:
            ft = mate(trozo, ALTO_MATTE)
            fino[y0:y1, x0:x1] = np.asarray(Image.fromarray(ft.astype(np.float32)).resize((x1 - x0, y1 - y0), Image.BILINEAR), dtype=np.float32)
    franja = (forma > 0.02) & (forma < 0.98)
    for _ in range(max(2, h // 220)):                                  # (≈4-5 px a 1024 por lado: el pelo suelto; con numpy, unos ms)
        franja = _dilatar(franja)
    a = np.where(franja, fino, forma)
    if previo is not None and previo.shape == a.shape:
        quieto = np.abs(a - previo) < 0.25
        a = np.where(quieto, previo * 0.35 + a * 0.65, a)
    return a


def _podar_mascaras():
    """Las máscaras de más de DIAS_MASCARAS días se borran (un proyecto de Resolve de hace meses ya no las pide)."""
    try:
        import time as _t
        limite = _t.time() - DIAS_MASCARAS * 86400
        for f in MASCARAS.glob('*.mov'):
            if f.stat().st_mtime < limite:
                f.unlink(missing_ok=True)
    except Exception:
        pass


def mascara_guardada(video, t0, t1, corte=1.0, al_progreso=None):
    """v5.31 (el usuario: «guarda la máscara para que siempre quede ahí y no ponga lento nada»): el recorte de la persona de t0 a t1 en la
    carpeta de las máscaras (MASCARAS, fuera de la caché que se limpia: el proyecto de Resolve sigue apuntando a ella), una sola vez por video,
    tramo y versión: volver a pulsar «Listo» o rehacer GO la reutiliza al momento. Devuelve la ruta o None."""
    import hashlib
    p = Path(str(video))
    try:
        st = p.stat()
        huella = hashlib.sha1(f'{p.resolve()}|{st.st_size}|{st.st_mtime_ns}|{float(t0):.3f}|{float(t1):.3f}|{float(corte):.3f}|v{VERSION_MATTE}'
                              .encode('utf-8')).hexdigest()[:16]
    except OSError:
        return None
    destino = MASCARAS / f'{p.stem[:40]}_{huella}.mov'
    if destino.is_file() and destino.stat().st_size > 1000:
        try:
            import os
            os.utime(destino, None)                                    # (en uso: no se poda)
        except OSError:
            pass
        if al_progreso:
            al_progreso(1.0)
        return destino
    MASCARAS.mkdir(parents=True, exist_ok=True)
    _podar_mascaras()
    return recorte_prores(video, t0, t1, destino, al_progreso=al_progreso, corte=corte)


def recorte_prores(video, t0, t1, destino, al_progreso=None, lado_max=1920, corte=1.0):
    """La persona recortada de t0 a t1 (segundos del ARCHIVO) como ProRes 4444 con alfa recto. Devuelve la ruta o None.
    Se codifica a la resolución del archivo (con el lado largo como mucho `lado_max`): Resolve lo encaja igual que el clip de V1.
    v5.31: la silueta de matte_persona; el fondo (alfa 0) va en NEGRO y, por debajo de `corte` (fracción del alto: ahí la persona es idéntica a
    lo que tiene debajo), nada: el archivo pesa una fracción (antes 70–100 MB por 2 s) y Resolve lo reproduce sin esfuerzo."""
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
            import rotacion_video as RV                                   # v5.5.8: el recorte sale derecho, como el clip en Resolve
            k = RV.giro(video)
            W, H = RV.medidas(vs.codec_context.width, vs.codec_context.height, k)
            esc = min(1.0, lado_max / max(W, H))
            ow, oh = int(W * esc) // 2 * 2, int(H * esc) // 2 * 2
            with av.open(str(tmp), 'w') as o:
                os_ = o.add_stream('prores_ks', rate=fps)
                os_.width, os_.height, os_.pix_fmt = ow, oh, 'yuva444p10le'
                os_.options = {'profile': '4', 'vendor': 'apl0', 'qscale': '4'}   # (v5.31: más calidad; el fondo negro casi no pesa)
                c.seek(max(0, int((t0 - 0.5) / tb)), stream=vs, backward=True, any_frame=False)
                previo, n, total = None, 0, max(1, int((t1 - t0) * float(fps)))
                estado = {}                                            # (la zona de la persona, la misma en todo el tramo)
                # v5.31: el ProRes se codifica en otro hilo mientras la IA recorta el fotograma siguiente (en orden; la cola es corta)
                import queue
                import threading
                cola, fallo = queue.Queue(maxsize=4), []

                def codificar():
                    try:
                        while True:
                            x = cola.get()
                            if x is None:
                                break
                            for pk in os_.encode(av.VideoFrame.from_ndarray(x, format='rgba')):
                                o.mux(pk)
                        for pk in os_.encode():
                            o.mux(pk)
                    except Exception as e:                             # (se sigue vaciando la cola: el hilo de la IA no se queda esperando)
                        fallo.append(e)
                        while cola.get() is not None:
                            pass
                hilo = threading.Thread(target=codificar, daemon=True)
                hilo.start()
                try:
                    for f in RV.fotogramas(c, vs):
                        ts = float(f.pts * tb) if f.pts is not None else 0.0
                        if ts < t0 - 0.5 / float(fps):
                            continue
                        if ts >= t1 or fallo:
                            break
                        rgb = RV.derecho_nd(f.to_ndarray(format='rgb24'), k)
                        a = matte_persona(rgb, previo, estado)
                        previo = a
                        alfa = refinar_alfa(a, ow, oh)
                        if corte < 0.999:
                            alfa[int(round(max(0.0, corte) * oh)):, :] = 0
                        img = rgb if (ow, oh) == (W, H) else np.asarray(Image.fromarray(rgb).resize((ow, oh), Image.BILINEAR))
                        img = np.where((alfa > 0)[..., None], img, 0).astype(np.uint8)   # (el fondo, negro: casi no pesa)
                        cola.put(np.dstack([img, alfa]))
                        n += 1
                        if al_progreso and n % 10 == 0:
                            al_progreso(min(1.0, n / total))
                finally:
                    cola.put(None)
                    hilo.join()
                if fallo:
                    raise fallo[0]
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
