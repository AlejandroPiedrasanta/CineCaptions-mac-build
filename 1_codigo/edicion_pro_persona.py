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

MODELO_CARAS = 'face_detection_yunet_2026may.onnx'   # v5.58: YuNet (OpenCV Zoo, licencia MIT: modelos/LICENCIA_yunet.txt), 230 KB
LADO_CARAS = 640                         # (las caras se buscan con la imagen a este lado: 10-20 ms en la CPU)
UMBRAL_CARA = 0.65
MODELO_CUERPOS = 'object_detection_nanodet_2022nov.onnx'   # v5.58: NanoDet-Plus (OpenCV Zoo, Apache 2.0: modelos/LICENCIA_nanodet.txt), 3,8 MB
LADO_CUERPOS = 416                       # (la entrada del modelo: 15-25 ms en la CPU)
UMBRAL_CUERPO = 0.5
_AVISOS_DETECTOR = set()


def ruta_modelo_detector(nombre) -> Path | None:
    """Un detector (de caras o de personas) que viaja con el programa junto a MODNet, o None."""
    try:
        from sfx_rules import base_recursos
        r = Path(base_recursos()) / 'edicion_pro' / 'modelos' / nombre
    except Exception:
        r = Path(__file__).resolve().parent.parent / '2_recursos' / 'edicion_pro' / 'modelos' / nombre
    return r if r.exists() else None


def _detectar(img, nombre, lado, umbral, op, sin_el):
    """La imagen RGB (a `lado` px de lado mayor, sin agrandarla) por el detector `nombre` en el motor 3.14 (motor_compat.<op>); None si no
    hay detector, y lo dice una vez en el Registro (`sin_el`: qué pasa entonces)."""
    ruta = ruta_modelo_detector(nombre)
    try:
        if ruta is None:
            raise FileNotFoundError(nombre)
        import motor_compat
        from PIL import Image
        h, w = img.shape[:2]
        k = min(1.0, lado / float(max(h, w)))
        chica = img if k >= 1.0 else np.asarray(Image.fromarray(img).resize((max(1, int(round(w * k))), max(1, int(round(h * k)))),
                                                                            Image.BILINEAR))
        return getattr(motor_compat, op)(chica, ruta, umbral=umbral)
    except Exception as e:
        if nombre not in _AVISOS_DETECTOR:
            _AVISOS_DETECTOR.add(nombre)
            try:
                import registro
                registro.aviso(f'«Captions detrás de ti»: sin el detector de {"caras" if op == "caras" else "personas"} '
                               f'({type(e).__name__}: {e}); {sin_el}', 'edición pro')
            except Exception:
                pass
        return None


def caras(img):
    """v5.58: las CARAS de una imagen RGB (YuNet, en el motor 3.14): [[x0, y0, x1, y1, puntuación, …5 puntos]] en fracciones; None si no hay
    detector (entonces personas_de_imagen cuenta como antes de la 5.58 y lo dice una vez en el Registro)."""
    return _detectar(img, MODELO_CARAS, LADO_CARAS, UMBRAL_CARA, 'caras',
                     'la persona se busca como antes (puede tomar por persona algún objeto).')


def cuerpos(img):
    """v5.58: las PERSONAS de una imagen RGB, también de espaldas o de lado (NanoDet, en el motor 3.14): [[x0, y0, x1, y1, puntuación]] en
    fracciones; None si no hay detector (entonces solo cuenta quien sale con la cara)."""
    return _detectar(img, MODELO_CUERPOS, LADO_CUERPOS, UMBRAL_CUERPO, 'cuerpos',
                     'solo cuenta como persona quien sale con la cara (no quien sale de espaldas).')


def disponible() -> bool:
    try:
        import motor_compat
        import av  # noqa: F401
        # (v5.86: también en el Mac, con el motor dentro del programa; hasta la 5.85 se apagaba allí «por no estar probado»)
        return motor_compat.instalado() and ruta_modelo() is not None
    except Exception:
        return False


def _a_modelo(rgb, alto):
    """v5.57: la imagen YA al tamaño con que el motor la pasa al modelo (worker._mate_activo: múltiplos de 32, BILINEAR): el modelo ve
    exactamente lo mismo (alfa idéntico, medido) y por el disco viaja ~1/14 del cuadro; antes iba el fotograma entero (6 MB) en cada pasada y el
    recorte de «detrás de ti» tardaba casi el doble (953 → 537 ms por fotograma)."""
    from PIL import Image
    alto = max(32, int(round(int(alto) / 32.0)) * 32)
    h, w = rgb.shape[:2]
    ancho = max(32, int(round(w * alto / h / 32.0)) * 32)
    rgb = np.ascontiguousarray(rgb, dtype=np.uint8)
    if (w, h) == (ancho, alto):
        return rgb
    return np.asarray(Image.fromarray(rgb).resize((ancho, alto), Image.BILINEAR))


def mate(rgb: np.ndarray, alto=None) -> np.ndarray:
    """Calcula la silueta en el motor auxiliar Python 3.14."""
    import motor_compat
    ruta = ruta_modelo()
    if ruta is None:
        raise RuntimeError('falta el modelo de recorte (modnet.onnx)')
    alto = int(alto or ALTO_MODELO)
    return motor_compat.mate(_a_modelo(rgb, alto), alto=alto, modelo=ruta)

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


def _tramos(m):
    """Cada tramo seguido de True de cada fila, con su número (1, 2, …; 0 fuera)."""
    inicio = m.copy()
    inicio[:, 1:] &= ~m[:, :-1]
    return np.cumsum(inicio, dtype=np.int32).reshape(m.shape) * m


def _inundar(semilla, dentro, maximo=4000):
    """Lo alcanzable desde `semilla` sin salir de `dentro` (reconstrucción geodésica, vecindad de 4). v5.57: por TRAMOS de filas y de columnas
    (un tramo tocado se llena entero de una vez) en vez de crecer un píxel por vuelta: lo mismo exacto (medido en 60 fotogramas y 300 casos al
    azar) y ~6 veces más rápido a 512."""
    r = semilla & dentro
    if not r.any():
        return r
    filas, columnas = _tramos(dentro), _tramos(dentro.T).T
    en_fila, en_columna = np.zeros(int(filas.max()) + 1, bool), np.zeros(int(columnas.max()) + 1, bool)
    total = int(np.count_nonzero(r))
    for _ in range(maximo):
        en_fila[filas[r]] = True
        en_fila[0] = False
        r = en_fila[filas]
        en_columna[columnas[r]] = True
        en_columna[0] = False
        r = en_columna[columnas]
        nuevo = int(np.count_nonzero(r))
        if nuevo == total:
            return r
        total = nuevo
    return r


def rellenar_huecos(m):
    """Cierra los agujeros de la silueta (una cara que el modelo dejó medio transparente). (v5.31: el relleno de Pillow va en Python píxel a
    píxel y era 5 veces más lento; a 512 px esto tarda ~6 ms (v5.57; antes ~30): por eso matte_persona rellena la FORMA, a 512, y no la pasada
    fina.)"""
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


def etiquetas(m, maximo=1000):
    """v5.58: TODAS las manchas de una máscara de una vez (vecindad de 4, como componentes): (el número de cada píxel —0 fuera—, cuántas hay).
    Por tramos de filas y de columnas: cada tramo se queda con el número menor de los tramos que cruza, hasta que nada cambia (pocas vueltas).
    componentes() inunda una a una y se queda en las 8 primeras; esto da lo mismo (medido en 302 máscaras), no deja ninguna sin mirar y es
    ~4,5 veces más rápido con muchas manchas pequeñas (el borde que parpadea)."""
    h, w = m.shape
    idx = np.flatnonzero(m)
    if not len(idx):
        return np.zeros((h, w), np.int32), 0
    rr = _tramos(m).ravel()[idx]                                       # (el tramo de fila de cada píxel: crece en orden de filas)
    ys, xs = np.divmod(idx, w)
    cc = _tramos(np.ascontiguousarray(m.T))[xs, ys]                    # (y su tramo de columna)
    orden = np.lexsort((ys, xs))                                       # (los píxeles en orden de columnas)
    cc_o = cc[orden]
    ini_r = np.flatnonzero(np.r_[True, rr[1:] != rr[:-1]])
    ini_c = np.flatnonzero(np.r_[True, cc_o[1:] != cc_o[:-1]])
    num = np.arange(1, int(rr[-1]) + 1, dtype=np.int32)               # (el número de cada tramo de fila)
    px = np.empty(len(idx), np.int32)
    for _ in range(maximo):
        por_c = np.minimum.reduceat(num[rr - 1][orden], ini_c)
        px[orden] = por_c[cc_o - 1]
        nuevo = np.minimum.reduceat(px, ini_r)
        if np.array_equal(nuevo, num):
            break
        num = nuevo
    unicos, inv = np.unique(num, return_inverse=True)
    out = np.zeros(h * w, np.int32)
    out[idx] = (inv.astype(np.int32) + 1)[rr - 1]
    return out.reshape(h, w), len(unicos)


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


def _cuerpo_de(c, lista, tope):
    """v5.58: la persona de NanoDet (de espaldas, de lado…) que ES la silueta c (rejilla de personas_de_imagen): su cabeza (el cuarto de arriba
    y la mitad del centro de su caja) cae en la silueta, en su mitad de arriba (fila ≤ tope), y la silueta llena al menos un cuarto de su
    caja. El balón, la mesa del DJ o el borde de la piscina tienen a alguien al lado o detrás, no encima: su cabeza no está en esa silueta."""
    gh, gw = c.shape
    for b in lista:
        x0, y0 = int(b[0] * gw), int(b[1] * gh)
        x1, y1 = max(x0 + 1, int(round(b[2] * gw))), max(y0 + 1, int(round(b[3] * gh)))
        bw, bh = x1 - x0, y1 - y0
        cabeza = c[y0:y0 + max(1, bh // 4), x0 + bw // 4:max(x0 + bw // 4 + 1, x1 - bw // 4)]
        if cabeza.size and cabeza.mean() >= 0.2 and y0 + bh / 8.0 <= tope and c[y0:y1, x0:x1].mean() >= 0.25:
            return b
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
    lista_caras = lista_cuerpos = None
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
        # v5.58 (el usuario: «que solo detecte humanos»): una silueta solo es una PERSONA si tiene una CARA (YuNet) en su mitad de arriba o,
        # sin cara (de espaldas, de lado), si NanoDet ve ahí a una persona (_cuerpo_de). El modelo de recorte daba por persona cojines, camas,
        # alfombras, un puf, el borde de una piscina (PRUEBAS (6)), un balón o una mesa de DJ (ESPAÑOL.mov). Cada detector mira una vez por
        # imagen y solo si hace falta: las caras si hay alguna silueta candidata; NanoDet, si a alguna le falta la cara
        if lista_caras is None:
            lista_caras = caras(img)
            lista_caras = False if lista_caras is None else lista_caras          # (False: sin detector, como antes)
        cara = cuerpo = None
        if lista_caras is not False:
            cerca = _dilatar(_dilatar(c))
            for f in lista_caras:
                fy, fx = int((f[1] + f[3]) / 2.0 * gh), int((f[0] + f[2]) / 2.0 * gw)
                if 0 <= fy < gh and 0 <= fx < gw and cerca[fy, fx] and fy <= y0 + 0.5 * alto_c:
                    cara = f
                    break
            if cara is None:
                if lista_cuerpos is None:
                    lista_cuerpos = cuerpos(img) or []
                cuerpo = _cuerpo_de(c, lista_cuerpos, y0 + 0.5 * alto_c)
                if cuerpo is None:
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
                           'cabeza': {'alto': round(float(cab_alto), 4), 'ancho': round(float(frente) / gw, 4)},
                           'cara': [round(float(x), 4) for x in cara[:5]] if cara else None,
                           'cuerpo': [round(float(x), 4) for x in cuerpo[:5]] if cuerpo else None})
    if not salida:
        return {'personas': [], 'arriba': None}
    return {'personas': salida, 'arriba': min(p['bbox'][1] for p in salida), 'abajo': max(p['bbox'][3] for p in salida),
            'izq': min(p['bbox'][0] for p in salida), 'der': max(p['bbox'][2] for p in salida)}


def _curva_alfa():
    """La curva de refinar_alfa para cada nivel 0..255 (v5.57: las MISMAS cuentas en float32, hechas una vez: el alfa sale idéntico y ya no son
    dos millones de cuentas por fotograma)."""
    x = np.clip((np.arange(256, dtype=np.float32) / 255.0 - 0.12) / 0.76, 0.0, 1.0)
    return ((x * x * (3.0 - 2.0 * x)) * 255).astype(np.uint8).tolist()


_CURVA_ALFA = _curva_alfa()


def refinar_alfa(a, ancho, alto):
    """El alfa del modelo (a ALTO_MODELO px) al tamaño final con el borde pulido (v5.4.52): escalado bicúbico (sin escalones), una curva suave
    que quita el halo gris de fuera y los huecos claros de dentro, y menos de un píxel de desenfoque en el borde (pelo y hombros). uint8 (de solo
    lectura)."""
    from PIL import Image, ImageFilter
    img = Image.fromarray((np.clip(a, 0.0, 1.0) * 255).astype(np.uint8), 'L').resize((int(ancho), int(alto)), Image.BICUBIC)
    return np.asarray(img.point(_CURVA_ALFA).filter(ImageFilter.GaussianBlur(max(0.6, int(ancho) / 1800.0))))


def puntos_fusion(det):
    """Los puntos para PosStrokes del MagicMask de Fusion (y con el origen ABAJO)."""
    return [(x, round(1.0 - y, 5)) for p in (det or {}).get('personas') or [] for (x, y) in p['puntos']]


ALTO_MATTE = 1024                        # v5.31: el BORDE del recorte con el modelo a 1024 px (a 512 el pelo y las orejas llevaban halo de fondo)
ALTO_FORMA = 512                         # …y la FORMA de la persona a 512 (a 1024 el modelo a veces deja huecos dentro del cuerpo)
VERSION_MATTE = 5                        # v5.57: 4 = el borde estable; v5.58: 5 = sin destellos (las máscaras guardadas antes se rehacen)
QUIETO_NIVELES = 4.0                     # v5.57: si la luz cambia menos que esto (0-255, suavizada) entre dos fotogramas, ese sitio está QUIETO…
MARGEN_CAMBIO = 0.4                      # …y ahí un píxel solo cambia de lado si la IA lo dice claro (alfa a más de esto de 0,5)
DESTELLO_MAX = 8                         # v5.58: en lo quieto, un cambio que no dura estos fotogramas es un destello (_sin_destellos)…
PRERROLLO = 10                           # …y el recorte empieza estos fotogramas ANTES del tramo (no salen): el primero ya tiene historia
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


def _quitar_pegotes(a, forma, fino, rgb):
    """v5.58 (ESPAÑOL.mov, 44 s: un trozo del edificio de detrás, pegado a la cabeza, salía como persona justo donde van los captions): la
    FORMA (la pasada a ALTO_FORMA px del cuadro entero) a veces pega a la cabeza un trozo de fondo que la pasada FINA (ALTO_MATTE px sobre la
    persona: el modelo es de retratos) ve claramente como fondo. Esas zonas —la forma dice persona, la fina dice fondo, tocan el fondo de fuera,
    están en el CUARTO DE ARRIBA de la silueta fina (la cabeza y los hombros) y por su color se parecen más al fondo que tienen al lado que a la
    persona que tienen al lado— se quedan con lo que dice la fina. Sin lo del color, la fina se equivocaba con un pelo borroso de espaldas y con
    un hombro de chaqueta en la penumbra (los quitaba). Más abajo sigue mandando la forma: ahí el modelo de retratos pierde a veces las piernas
    o medio cuerpo (8 s: el 43 % de la persona)."""
    from PIL import Image
    persona = forma > 0.5
    dudas = persona & (fino < 0.2)
    if not dudas.any():
        return a
    filas = np.nonzero((fino > 0.5).any(axis=1))[0]
    if not len(filas):
        return a
    tope = filas[0] + 0.25 * (filas[-1] - filas[0] + 1)
    h, w = a.shape
    k = max(1, h // 256)
    g, gp, gf = dudas[::k, ::k], persona[::k, ::k], fino[::k, ::k] > 0.5
    fuera = _dilatar(~gp)
    quitar = np.zeros_like(g)
    color = None
    # (v5.58, más rápido: todas las manchas de una vez —etiquetas— y las cuentas de cada una juntas; solo se miran a fondo las que tocan el
    # fondo de fuera, están en el cuarto de arriba y no son migas)
    lab, n = etiquetas(g)
    tam = np.bincount(lab.ravel(), minlength=n + 1)
    toca = np.bincount(lab.ravel(), weights=fuera.ravel(), minlength=n + 1)
    fila = np.bincount(lab.ravel(), weights=np.repeat(np.arange(g.shape[0], dtype=np.float64), g.shape[1]), minlength=n + 1)
    minimo = max(2, int(0.002 * gp.sum()))
    for j in range(1, n + 1):
        if tam[j] < minimo or not toca[j] or (fila[j] / tam[j] + 0.5) * k >= tope:
            continue
        c = lab == j
        if color is None:
            color = np.asarray(Image.fromarray(rgb).resize((g.shape[1], g.shape[0]), Image.BILINEAR), np.float32)
        anillo = c
        for _ in range(2):
            anillo = _dilatar(anillo)
        anillo &= ~c
        fondo, gente = anillo & ~gp, anillo & gf
        if fondo.sum() < 3 or gente.sum() < 3:
            continue
        mio = np.median(color[c], axis=0)
        if np.linalg.norm(mio - np.median(color[fondo], axis=0)) < 0.8 * np.linalg.norm(mio - np.median(color[gente], axis=0)):
            quitar |= c
    if not quitar.any():
        return a
    grande = np.repeat(np.repeat(_dilatar(quitar), k, axis=0), k, axis=1)[:h, :w]
    return np.where(grande, fino, a)


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


def _forma_persona(rgb):
    """La FORMA de matte_persona (su 1.ª pasada, a ALTO_FORMA px: sin manchas sueltas ni huecos) ya en la rejilla fina (el cuadro entero a
    ALTO_MATTE px de alto). No depende del fotograma anterior: v5.57, recorte_prores la calcula en otro hilo, un fotograma por delante."""
    from PIL import Image
    forma = mate(rgb, ALTO_FORMA)
    forma = _limpiar_islas(forma, forma > 0.5)
    forma = _rellenar_huecos_persona(forma)                            # (los huecos, en la forma: ~6 ms a 512)
    H0, W0 = rgb.shape[:2]
    h = ALTO_MATTE
    w = max(1, int(round(W0 * h / float(H0))))
    return np.asarray(Image.fromarray(forma.astype(np.float32)).resize((w, h), Image.BILINEAR), dtype=np.float32)


def _luz(rgb, rejilla, luma_ant):
    """(la luz del fotograma a la rejilla fina (alto, ancho), dónde la IMAGEN está quieta desde `luma_ant` —None sin anterior—): lo que usa el
    borde estable de matte_persona (v5.57). v5.58: aparte, para que recorte_prores lo haga en el hilo que lee (sale lo mismo)."""
    from PIL import Image, ImageFilter
    h, w = rejilla
    luma = np.asarray(Image.fromarray(rgb).convert('L').resize((w, h), Image.BILINEAR), np.float32)
    quieto = None
    if luma_ant is not None and luma_ant.shape == luma.shape:
        dif = np.clip(np.abs(luma - luma_ant), 0, 255).astype(np.uint8)
        quieto = np.asarray(Image.fromarray(dif).filter(ImageFilter.GaussianBlur(2)), np.float32) < QUIETO_NIVELES
    return luma, quieto


def matte_persona(rgb, previo=None, estado=None, forma=None, luz=None):
    """v5.31 (el usuario: «la máscara perfecta para humanos, sin bugs ni fallas»): la silueta de las personas para el recorte, en DOS pasadas
    del modelo: la FORMA a ALTO_FORMA px (robusta: ni huecos en el cuerpo ni manchas de fondo) y el BORDE a ALTO_MATTE px (pelo, orejas,
    dedos), que solo cuenta en una franja alrededor del contorno de la forma; sin manchas sueltas (_limpiar_islas), sin agujeros dentro (la cara,
    una mano delante) y estable de un fotograma a otro sin dejar estela (v5.57: se suaviza solo donde la IMAGEN está quieta). Devuelve el alfa
    (0..1) a la resolución de la pasada fina. `forma`: la de _forma_persona(rgb) si ya está hecha (v5.57); `luz`: la de _luz (v5.58). `estado`
    guarda entre fotogramas la zona de la persona y la luz del fotograma anterior."""
    from PIL import Image
    forma = _forma_persona(rgb) if forma is None else forma
    H0, W0 = rgb.shape[:2]
    h, w = forma.shape                                                 # (la rejilla fina)
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
    if caja is not None:
        a = _quitar_pegotes(a, forma, fino, rgb)                       # (v5.58: el fondo que la forma pega a la cabeza)
    # v5.57 (el usuario: «verifica que está en máxima calidad»; eligió el borde «muy estable»): donde la IMAGEN no se movió, un píxel solo
    # cambia de lado (alfa por encima o por debajo de 0,5) si la IA lo dice claro; si no, se queda como en el fotograma anterior. Sin mezclar
    # alfas: no crea grises nuevos. La mezcla con el anterior (el «C» de los ejemplos) quitaba más temblor pero volvía translúcido el borde de
    # lo que se mueve despacio (4K de boda: grises visibles del 3,5 al 8,9 % de la persona, y 2 → 6 islas); la mediana de 3 fotogramas también
    # creaba islas. Medido en 5 tramos: lo que cambia de lado en lo quieto baja un 17-29 %, mismas islas y mismo halo, y sin la estela de antes
    # (2,8-4,8 /255 → 0). Antes: 35 % del anterior donde el ALFA cambió < 0,25, también en lo que se movía.
    estado['luma'], quieto = _luz(rgb, (h, w), estado.get('luma')) if luz is None else luz
    estado['quieto'] = quieto                                          # (v5.58: lo usa _sin_destellos, con los fotogramas siguientes)
    return estabilizar(a, previo, quieto)


def estabilizar(a, previo, quieto):
    """El borde estable de matte_persona (v5.57): donde la imagen está quieta, un píxel dudoso no cambia de lado (se queda como en `previo`)."""
    if previo is None or quieto is None or previo.shape != a.shape:
        return a
    dudoso = ((a >= 0.5) != (previo >= 0.5)) & (np.abs(a - 0.5) <= MARGEN_CAMBIO)
    return np.where(quieto & dudoso, previo, a)


def _sin_destellos(ant, a, siguientes, quietos):
    """v5.58 (probando el Tema 1 con «detrás de ti» en ESPAÑOL.mov: un trozo de la columna junto a la cabeza, una mancha encima del pelo o la
    sombra del suelo entraban en el recorte de 1 a 5 fotogramas y salían: delante de los captions se ve como un destello): donde la imagen está
    QUIETA, un píxel que cambia de lado (alfa 0,5) y vuelve al de `ant` en uno de los `siguientes` (los alfas crudos de los DESTELLO_MAX
    fotogramas que vienen) sin que la imagen se haya movido entre medias (`quietos`: los pasos ant → a → siguientes) es un destello de la IA: se
    queda como en `ant`. Lo que cambia y SIGUE cambiado (una corrección de verdad) pasa sin retraso; lo que se mueve no se toca."""
    if ant is None or not siguientes or not quietos or quietos[0] is None or ant.shape != a.shape:
        return a
    lado = ant >= 0.5
    cambia = (a >= 0.5) != lado
    i = np.flatnonzero(cambia)
    if not len(i):
        return a
    # (v5.58, más rápido: solo los píxeles que cambian —unos pocos por ciento—, no el cuadro entero por cada uno de los siguientes)
    lado_i, quieto_i, volver_i = lado.ravel()[i], quietos[0].ravel()[i], np.zeros(len(i), bool)
    for s, q in zip(siguientes, quietos[1:]):
        if q is None or s.shape != a.shape:
            break
        quieto_i = quieto_i & q.ravel()[i]
        volver_i |= ((s.ravel()[i] >= 0.5) == lado_i) & quieto_i
    if not volver_i.any():
        return a
    volver = np.zeros(a.size, bool)
    volver[i] = volver_i
    volver = volver.reshape(a.shape)
    # por MANCHAS (rejilla de 4 px): cada mancha de lo que cambió vuelve ENTERA si casi toda (≥ 80 %) es destello, o nada. Píxel a píxel, una
    # persona que la IA ve a trozos (traje oscuro sobre pared oscura, PRUEBAS (4) a los 63 s) quedaba rota en islas (de 1 a 6). Todas las
    # manchas de una vez (etiquetas; antes, con componentes, solo las 8 de más arriba)
    k = 4
    h, w = a.shape
    hk, wk = h // k, w // k
    c4 = cambia[:hk * k, :wk * k].reshape(hk, k, wk, k).sum(axis=(1, 3))
    v4 = volver[:hk * k, :wk * k].reshape(hk, k, wk, k).sum(axis=(1, 3))
    lab, n = etiquetas(c4 > 0)
    if not n:
        return a
    destello = np.bincount(lab.ravel(), weights=v4.ravel(), minlength=n + 1) >= 0.8 * np.bincount(lab.ravel(), weights=c4.ravel(),
                                                                                                  minlength=n + 1)
    destello[0] = False
    vale = destello[lab]
    if not vale.any():
        return a
    grande = np.zeros((h, w), bool)
    grande[:hk * k, :wk * k] = np.repeat(np.repeat(vale, k, axis=0), k, axis=1)
    return np.where(cambia & grande, ant, a)


def _podar_mascaras():
    """Las máscaras de más de DIAS_MASCARAS días se borran (un proyecto de Resolve de hace meses ya no las pide)."""
    try:
        import time as _t
        limite = _t.time() - DIAS_MASCARAS * 86400
        for f in MASCARAS.glob('*.mov'):
            if f.stat().st_mtime < limite:
                f.unlink(missing_ok=True)
                _ruta_calidad(f).unlink(missing_ok=True)
    except Exception:
        pass


PARPADEO_MAX = 8.0                       # v5.58: % de la persona visible que cambia con la imagen quieta, en el peor fotograma, para dar un
                                         # recorte por malo (bien: ≤ 2,7 % en 9 videos; un trozo de fondo o una persona a trozos: 12-27 %)
BANDAS_CALIDAD = 32


def _ruta_calidad(mascara):
    return Path(mascara).with_name(Path(mascara).stem + '.calidad.json')


def calidad_mascara(mascara, visible=1.0):
    """v5.58: cuánto PARPADEA de verdad el recorte (lo que recorte_prores anotó al hacerlo): el % del área de la persona que cambia de lado con
    la imagen QUIETA, en el peor fotograma, solo por encima de `visible` (fracción del alto: lo que «detrás de ti» deja ver; por debajo se
    recorta). None si esa máscara no lo trae (hecha antes de la 5.58)."""
    import json
    try:
        d = json.loads(_ruta_calidad(mascara).read_text(encoding='utf-8'))
        nb = int(d.get('bandas') or BANDAS_CALIDAD)
        b = max(1, min(nb, int(np.ceil(float(visible) * nb))))
        minimo = 0.001 * float(d.get('pixeles') or 0)                   # (con casi nada de persona a la vista, el % no dice nada)
        peor = 0.0
        for cambio, area in zip(d['cambio'], d['area']):
            a = float(sum(area[:b]))
            if a > max(1.0, minimo):
                peor = max(peor, 100.0 * float(sum(cambio[:b])) / a)
        return round(peor, 2)
    except Exception:
        return None


def lado_recorte(ancho_tl, alto_tl):
    """v5.82 (el usuario: «que los estilos en 4K no pierdan calidad»): el lado largo máximo del recorte = el del timeline (3840 en un 4K), nunca
    menos de 1920. Antes era siempre 1920: en un timeline 4K Resolve estiraba la persona ×2 y quedaba más borrosa que el video de detrás."""
    try:
        return max(1920, int(max(int(ancho_tl or 0), int(alto_tl or 0))))
    except (TypeError, ValueError):
        return 1920


def mascara_guardada(video, t0, t1, corte=1.0, al_progreso=None, lado_max=1920):
    """v5.31 (el usuario: «guarda la máscara para que siempre quede ahí y no ponga lento nada»): el recorte de la persona de t0 a t1 en la
    carpeta de las máscaras (MASCARAS, fuera de la caché que se limpia: el proyecto de Resolve sigue apuntando a ella), una sola vez por video,
    tramo y versión: volver a pulsar «Listo» o rehacer GO la reutiliza al momento. Devuelve la ruta o None.
    v5.82: `lado_max` (lado_recorte del timeline) entra en la huella si no es 1920: las guardadas para un timeline 1080 siguen valiendo ahí."""
    import hashlib
    p = Path(str(video))
    lado_max = int(lado_max or 1920)
    try:
        st = p.stat()
        huella = hashlib.sha1((f'{p.resolve()}|{st.st_size}|{st.st_mtime_ns}|{float(t0):.3f}|{float(t1):.3f}|{float(corte):.3f}|v{VERSION_MATTE}'
                               + ('' if lado_max == 1920 else f'|L{lado_max}')).encode('utf-8')).hexdigest()[:16]
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
    return recorte_prores(video, t0, t1, destino, al_progreso=al_progreso, lado_max=lado_max, corte=corte)


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
                c.seek(max(0, int((t0 - 0.5 - PRERROLLO / float(fps)) / tb)), stream=vs, backward=True, any_frame=False)
                previo, n, total = None, 0, max(1, int((t1 - t0) * float(fps)))
                estado = {}                                            # (la zona de la persona, la misma en todo el tramo)
                # v5.57: el recorte en cadena, en orden y con colas cortas, cada paso en su hilo: leer el fotograma y su FORMA (la 1.ª pasada de la
                # IA, que no depende del anterior) → el BORDE y la estela (que sí dependen: en este hilo) → pulir el alfa y componer → el ProRes
                # (v5.31). Mientras el motor corre la IA, la CPU ya hace lo del fotograma de al lado; sale lo mismo que en serie (medido: idéntico)
                import queue
                import threading
                formas, pulir, cola, fallo = queue.Queue(maxsize=3), queue.Queue(maxsize=3), queue.Queue(maxsize=4), []

                def leer():
                    try:
                        luma = None
                        for f in RV.fotogramas(c, vs):
                            ts = float(f.pts * tb) if f.pts is not None else 0.0
                            if ts < t0 - (0.5 + PRERROLLO) / float(fps):
                                continue
                            if ts >= t1 or fallo:
                                break
                            rgb = RV.derecho_nd(f.to_ndarray(format='rgb24'), k)
                            forma = _forma_persona(rgb)
                            luz = _luz(rgb, forma.shape, luma)                 # (v5.58: también aquí, fuera del hilo de la pasada fina)
                            luma = luz[0]
                            formas.put((rgb, forma, luz, ts >= t0 - 0.5 / float(fps)))   # (v5.58: False = prerrollo, no sale)
                    except Exception as e:
                        fallo.append(e)
                    finally:
                        formas.put(None)

                def componer():
                    try:
                        while True:
                            x = pulir.get()
                            if x is None:
                                break
                            if fallo:
                                continue
                            rgb, a = x
                            alfa = refinar_alfa(a, ow, oh)
                            img = rgb if (ow, oh) == (W, H) else np.asarray(Image.fromarray(rgb).resize((ow, oh), Image.BILINEAR))
                            rgba = np.empty((oh, ow, 4), np.uint8)
                            np.multiply(img, (alfa > 0)[..., None], out=rgba[..., :3])   # (el fondo, alfa 0, en NEGRO: casi no pesa)
                            rgba[..., 3] = alfa
                            if corte < 0.999:
                                rgba[int(round(max(0.0, corte) * oh)):] = 0
                            cola.put(rgba)
                    except Exception as e:                             # (se sigue vaciando: nadie se queda esperando)
                        fallo.append(e)
                        while pulir.get() is not None:
                            pass
                    finally:
                        cola.put(None)

                def codificar():
                    try:
                        while True:
                            x = cola.get()
                            if x is None:
                                break
                            if fallo:
                                continue
                            for pk in os_.encode(av.VideoFrame.from_ndarray(x, format='rgba')):
                                o.mux(pk)
                        for pk in os_.encode():
                            o.mux(pk)
                    except Exception as e:
                        fallo.append(e)
                        while cola.get() is not None:
                            pass

                # v5.58: cada fotograma sale con los DESTELLOS fuera (_sin_destellos): se espera a los DESTELLO_MAX siguientes (sus alfas
                # crudos) antes de darlo por bueno; el borde estable (estabilizar) va con el anterior ya limpio; los del prerrollo no salen. En
                # su propio hilo (limpiar), entre la pasada fina y pulir: el hilo de la IA solo hace la IA
                crudas = queue.Queue(maxsize=3)                        # (rgb, alfa crudo, quieto: el paso desde el anterior, sale)
                calidad = {'bandas': BANDAS_CALIDAD, 'cambio': [], 'area': [], 'pixeles': 0}   # (v5.58: para calidad_mascara)

                def soltar(pendientes):
                    nonlocal previo, n
                    rgb_k, cruda, q_k, sale = pendientes.pop(0)
                    a = estabilizar(cruda, previo, q_k)
                    a = _sin_destellos(previo, a, [s[1] for s in pendientes], [q_k] + [s[2] for s in pendientes])
                    if sale:                                           # (por bandas de filas: lo que cambia con la imagen quieta y la persona)
                        bordes = np.linspace(0, a.shape[0], BANDAS_CALIDAD + 1).astype(int)[:-1]
                        cambio = ((np.abs(a - previo) > 0.3) & q_k).sum(axis=1) if (previo is not None and q_k is not None
                                                                                      and previo.shape == a.shape) else np.zeros(a.shape[0], int)
                        calidad['cambio'].append([int(x) for x in np.add.reduceat(cambio, bordes)])
                        calidad['area'].append([int(x) for x in np.add.reduceat((a > 0.5).sum(axis=1), bordes)])
                        calidad['pixeles'] = int(a.size)
                    previo = a
                    if not sale:
                        return
                    pulir.put((rgb_k, a))
                    n += 1

                def limpiar():
                    pendientes, fin = [], False
                    try:
                        while True:
                            x = crudas.get()
                            if x is None:
                                fin = True
                                break
                            if fallo:
                                continue
                            pendientes.append(x)
                            if len(pendientes) > DESTELLO_MAX:
                                soltar(pendientes)
                        while pendientes and not fallo:
                            soltar(pendientes)
                    except Exception as e:                             # (se sigue vaciando: nadie se queda esperando)
                        fallo.append(e)
                        while not fin and crudas.get() is not None:
                            pass
                    finally:
                        pulir.put(None)

                hilos = [threading.Thread(target=f, daemon=True) for f in (leer, limpiar, componer, codificar)]
                for hilo in hilos:
                    hilo.start()
                leido, hechos = [], 0
                try:
                    while True:
                        x = formas.get()
                        if x is None:
                            leido.append(True)
                            break
                        if fallo:                                      # (algo falló: se vacía la cola y se acaba)
                            continue
                        rgb, forma, luz, sale = x
                        cruda = matte_persona(rgb, None, estado, forma=forma, luz=luz)
                        crudas.put((rgb, cruda, estado.get('quieto'), sale))
                        hechos += bool(sale)
                        if al_progreso and sale and hechos % 10 == 0:
                            al_progreso(min(1.0, hechos / total))
                except BaseException as e:
                    fallo.append(e)
                    while not leido and formas.get() is not None:
                        pass
                finally:
                    crudas.put(None)
                    for hilo in hilos:
                        hilo.join()
                if fallo:
                    raise fallo[0]
        if n == 0:
            tmp.unlink(missing_ok=True)
            return None
        tmp.replace(destino)
        try:
            import json
            _ruta_calidad(destino).write_text(json.dumps(calidad), encoding='utf-8')
        except OSError:
            pass
        return destino
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        raise
