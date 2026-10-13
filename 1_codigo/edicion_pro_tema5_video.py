# CineCaptions · By Cinema Productions
# 1_codigo/edicion_pro_tema5_video.py — el Tema 5 MIRA el video antes de editarlo (ffmpeg, vía PyAV): dónde corta cada toma, lo claro u oscuro que
# es, su tono y cuánto se mueve la cámara. Con eso elige el estilo de las escenas de ESTE video para que no todos salgan iguales:
#   * fondo de las escenas: papel claro (la referencia de la skill) o cristal oscuro (el tablero de inspiración: UI oscura con brillo del acento);
#     en un video oscuro y frío se alternan los dos; en uno claro, papel.
#   * dónde va cada escena: mitad de arriba (pantalla dividida), pantalla completa o los objetos flotando ENCIMA del video oscurecido; las tomas con
#     mucho movimiento no se parten (la persona se saldría de su mitad).
"""
    analizar(video, fps_analisis=4) -> {'dur', 'tomas': [{'ini', 'fin', 'brillo', 'saturacion', 'tono', 'movimiento'}], 'brillo', 'oscuro',
                                        'movimiento', 'cortes': [s]}
    estilo(analisis, semilla) -> {'fondos': ['papel'] | ['papel', 'cristal'], 'encima': bool, 'orden': [...disposiciones]}
"""
import hashlib


def analizar(video, fps_analisis=4.0, lado=96):
    """Un vistazo barato (4 fotogramas por segundo a 96 px): tomas por saltos de color, brillo/saturación/tono de cada una y su movimiento."""
    try:
        import av
        import numpy as np
    except Exception:
        return {}
    fotos, tiempos = [], []
    try:
        with av.open(str(video)) as c:
            s = c.streams.video[0]
            s.thread_type = 'AUTO'
            paso, siguiente = 1.0 / fps_analisis, 0.0

            def cuadros():                                               # un paquete dañado no tumba el análisis (se salta)
                for pk in c.demux(s):
                    try:
                        yield from pk.decode()
                    except av.error.InvalidDataError:
                        continue
            for fr in cuadros():
                t = float(fr.time or 0.0)
                if t + 1e-6 < siguiente:
                    continue
                siguiente = t + paso
                img = fr.to_image()
                img.thumbnail((lado, lado * 2))
                fotos.append(np.asarray(img.convert('RGB'), dtype=np.float32) / 255.0)
                tiempos.append(t)
    except Exception:
        return {}
    if len(fotos) < 2:
        return {}
    h = min(f.shape[0] for f in fotos)
    w = min(f.shape[1] for f in fotos)
    fotos = [f[:h, :w] for f in fotos]

    def hist(f):
        q = (f * 7.999).astype(int)
        idx = q[..., 0] * 64 + q[..., 1] * 8 + q[..., 2]
        return np.bincount(idx.ravel(), minlength=512) / idx.size

    hs = [hist(f) for f in fotos]
    saltos = [0.0] + [float(np.abs(hs[i] - hs[i - 1]).sum()) for i in range(1, len(hs))]
    movs = [0.0] + [float(np.abs(fotos[i] - fotos[i - 1]).mean()) for i in range(1, len(fotos))]
    umbral = max(0.55, float(np.percentile(saltos, 97)))
    cortes = [tiempos[i] for i in range(1, len(saltos)) if saltos[i] > umbral and (i < 2 or saltos[i - 1] < umbral)]
    limites = [tiempos[0]] + cortes + [tiempos[-1] + 1.0 / fps_analisis]
    tomas = []
    for a, b in zip(limites, limites[1:]):
        idx = [i for i, t in enumerate(tiempos) if a <= t < b]
        if not idx:
            continue
        px = np.concatenate([fotos[i].reshape(-1, 3) for i in idx])
        mx, mn = px.max(1), px.min(1)
        sat = (mx - mn) / (mx + 1e-6)
        vivos = px[sat > 0.2]
        tono = None
        if len(vivos) > 0.05 * len(px):
            import colorsys
            tono = round(colorsys.rgb_to_hsv(*vivos.mean(0))[0] * 360, 1)
        tomas.append({'ini': round(a, 2), 'fin': round(b, 2), 'brillo': round(float(px.mean()), 3), 'saturacion': round(float(sat.mean()), 3),
                      'tono': tono, 'movimiento': round(float(np.mean([movs[i] for i in idx[1:]] or [0.0])), 4)})
    brillo = float(np.mean([f.mean() for f in fotos]))
    return {'dur': round(tiempos[-1], 2), 'tomas': tomas, 'cortes': [round(t, 2) for t in cortes], 'brillo': round(brillo, 3),
            'oscuro': brillo < 0.33, 'movimiento': round(float(np.mean(movs[1:])), 4)}


def toma_en(analisis, t):
    for x in (analisis or {}).get('tomas') or []:
        if x['ini'] <= t < x['fin']:
            return x
    return None


def estilo(analisis, semilla=''):
    """El estilo de las escenas de ESTE video (cambia con el video: no todos salen iguales, pero dentro de uno es coherente)."""
    a = analisis or {}
    h = int(hashlib.sha1(str(semilla).encode('utf-8')).hexdigest()[:8], 16)
    tonos = [x['tono'] for x in a.get('tomas') or [] if x.get('tono') is not None]
    frio = bool(tonos) and sum(1 for t in tonos if 170 <= t < 300) >= len(tonos) / 2
    fondos = ['papel', 'cristal'] if a.get('oscuro') and (frio or h % 2) else (['cristal', 'papel'] if a.get('oscuro') else ['papel'])
    quieto = float(a.get('movimiento') or 0.0) < 0.035
    orden = [['arriba', 'encima', 'completa'], ['encima', 'arriba', 'completa'], ['arriba', 'completa', 'encima']][h % 3]
    return {'fondos': fondos, 'encima': True, 'partir': quieto, 'orden': orden}
