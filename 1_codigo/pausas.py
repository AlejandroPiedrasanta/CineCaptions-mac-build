# CineCaptions · By Cinema Productions
# 1_codigo/pausas.py — «Quitar pausas» (jump cuts en los silencios) para GO (v5.4.8).
"""
Con el video ya transcrito se sabe cuándo se habla y cuándo no. Si el usuario lo pide (Efectos › «Quitar pausas»), GO recorta los silencios largos del video que arma en
Resolve ANTES de poner los captions:

    segmentos = [(ini, fin), …]      los tramos de la FUENTE que se quedan (en segundos, ya ajustados a la rejilla de fotogramas)
    calcular(words, duracion, fps, nivel)  -> {'segmentos', 'quitado', 'saltos', 'duracion_nueva'} | None
    remapear_palabras / remapear_cortes     pasan los tiempos de la fuente a los del timeline recortado
    recortar_en_resolve(segmentos)          rehace V1 y A1 del timeline actual con esos tramos pegados uno tras otro

Solo se toca el timeline que GO armó con el video soltado (un único clip en V1): jamás el de otro trabajo. `saltos` son los instantes (en el timeline nuevo) donde se
unen dos tramos: el zoom alterno («punch-in» en cada corte) los usa.
"""
from __future__ import annotations

UMBRALES = {'suave': 0.85, 'normal': 0.50, 'fuerte': 0.32}        # una pausa más larga que esto (s) se recorta…
MAXIMOS = {'suave': 3.0, 'normal': 3.5, 'fuerte': 6.0}           # …salvo que sea MUY larga: eso casi siempre es una toma de apoyo (b-roll) con locución encima o sin ella, y se deja entera
RELLENO_INI = 0.10                                              # lo que se deja ANTES de la primera palabra de cada tramo (s)
RELLENO_FIN = 0.16                                              # y DESPUÉS de la última: las palabras no suenan cortadas
MIN_QUITADO_S = 1.0                                             # si en total se quita menos que esto, no vale la pena tocar nada
MIN_TRAMO_S = 0.25


def calcular(words, duracion, fps, nivel):
    """Los tramos que se quedan según los silencios entre palabras. None si `nivel` no existe o no hay casi nada que quitar."""
    umbral, maximo = UMBRALES.get(nivel), MAXIMOS.get(nivel, 3.5)
    palabras = [w for w in (words or []) if str(w.get('word', '')).strip() and w.get('end') is not None]
    if umbral is None or len(palabras) < 4:
        return None
    fps = float(fps or 30.0)
    duracion = float(duracion or palabras[-1]['end'])
    brutos = []
    for w in palabras:
        a, b = max(0.0, float(w['start']) - RELLENO_INI), min(duracion, float(w['end']) + RELLENO_FIN)
        hueco = float(w['start']) - brutos[-1][2] if brutos else 0.0
        if brutos and (hueco <= umbral or hueco > maximo):             # la pausa es corta (sigue el tramo) o tan larga que es una toma de apoyo (se deja)
            brutos[-1][1] = max(brutos[-1][1], b)
            brutos[-1][2] = float(w['end'])
        else:
            brutos.append([a, b, float(w['end'])])
    # el principio y el final: se recortan solo si lo que sobra es corto (aire muerto); si es largo, es imagen que se queda
    brutos[0][0] = max(0.0, float(palabras[0]['start']) - 0.25) if float(palabras[0]['start']) <= maximo else 0.0
    brutos[-1][1] = min(duracion, float(palabras[-1]['end']) + 0.45) if duracion - float(palabras[-1]['end']) <= maximo else duracion
    # a la rejilla de fotogramas, sin tramos diminutos y sin solaparse
    segs = []
    for a, b, _fin_palabra in brutos:
        fa, fb = int(round(a * fps)), int(round(b * fps))
        if fb <= fa:
            continue
        if segs and fa <= segs[-1][1]:
            segs[-1][1] = max(segs[-1][1], fb)
        else:
            segs.append([fa, fb])
    segs = [s for s in segs if (s[1] - s[0]) / fps >= MIN_TRAMO_S] or segs
    if not segs:
        return None
    quitado = duracion - sum(s[1] - s[0] for s in segs) / fps
    if quitado < MIN_QUITADO_S:
        return None
    segmentos, saltos, acumulado = [], [], 0.0
    for k, (fa, fb) in enumerate(segs):
        segmentos.append((fa / fps, fb / fps))
        if k:
            saltos.append(round(acumulado, 3))
        acumulado += (fb - fa) / fps
    return {'segmentos': segmentos, 'quitado': round(quitado, 2), 'saltos': saltos, 'duracion_nueva': round(acumulado, 3), 'fps': fps}


def mapear(t, segmentos):
    """El tiempo de la fuente `t` en el timeline recortado; None si cae en un tramo quitado."""
    acumulado = 0.0
    for a, b in segmentos:
        if a - 1e-6 <= t <= b + 1e-6:
            return acumulado + (min(max(t, a), b) - a)
        acumulado += b - a
    return None


def remapear_palabras(words, segmentos):
    """Las palabras con los tiempos del timeline recortado (las que cayeran en un silencio quitado, que no debería haber, se descartan). Guarda los de la fuente en src_start/src_end."""
    salida = []
    for w in words or []:
        s = mapear(float(w['start']), segmentos)
        if s is None:
            continue
        e = mapear(float(w.get('end', w['start'])), segmentos)
        nuevo = dict(w)
        nuevo['src_start'], nuevo['src_end'] = w['start'], w.get('end')
        nuevo['start'] = round(s, 3)
        nuevo['end'] = round(e if e is not None and e >= s else s + 0.05, 3)
        salida.append(nuevo)
    return salida


def remapear_cortes(cortes, segmentos):
    """[(t, fuerza)] de la fuente -> [(t', fuerza)] del timeline recortado (los que cayeran en lo quitado desaparecen)."""
    salida = []
    for t, f in cortes or []:
        n = mapear(float(t), segmentos)
        if n is not None:
            salida.append((round(n, 3), f))
    return salida


_CORTAR = r'''
SEGS = %(segs)r
tl = project.GetCurrentTimeline()
mp = project.GetMediaPool()
res = {'ok': False}
v1 = [it for it in (tl.GetItemListInTrack('video', 1) or []) if it]
a1 = [it for it in (tl.GetItemListInTrack('audio', 1) or []) if it]
if len(v1) != 1:
    res['error'] = 'V1 no tiene un solo clip (%%d): no se toca' %% len(v1)
else:
    it = v1[0]
    mpi = it.GetMediaPoolItem()
    if mpi is None:
        res['error'] = 'el clip de V1 no viene del Media Pool'
    else:
        try:
            fps_clip = float(mpi.GetClipProperty('FPS') or 0) or float(tl.GetSetting('timelineFrameRate') or 30)
        except Exception:
            fps_clip = float(tl.GetSetting('timelineFrameRate') or 30)
        fps_tl = float(tl.GetSetting('timelineFrameRate') or fps_clip)
        total = int(float(mpi.GetClipProperty('Frames') or 0))
        inicio = int(tl.GetStartFrame())
        antes = (it.GetStart(), it.GetEnd())
        tl.DeleteClips(v1 + a1, False)
        pos = inicio
        puestos = 0
        for a, b in SEGS:
            sf = int(round(a * fps_clip))
            ef = int(round(b * fps_clip)) - 1
            if total:
                ef = min(ef, total - 1)
            if ef < sf:
                continue
            nuevos = mp.AppendToTimeline([{'mediaPoolItem': mpi, 'startFrame': sf, 'endFrame': ef, 'recordFrame': pos, 'trackIndex': 1}])
            if not nuevos:
                res['error'] = 'Resolve no colocó el tramo %%d' %% puestos
                break
            puestos += 1
            pos += int(round((ef - sf + 1) * fps_tl / fps_clip))
        res['tramos'] = puestos
        res['inicio'], res['fin'] = inicio, pos
        v1n = tl.GetItemListInTrack('video', 1) or []
        a1n = tl.GetItemListInTrack('audio', 1) or []
        res['v1'], res['a1'] = len(v1n), len(a1n)
        for x in v1n:
            try:
                x.SetProperty('Scaling', resolve.SCALE_FIT)
            except Exception:
                pass
        if 'error' not in res and puestos == len(SEGS) and len(v1n) == puestos:
            res['ok'] = True
        else:
            res.setdefault('error', 'quedaron %%d tramos de video y %%d de audio' %% (len(v1n), len(a1n)))
            # a medias: se intenta dejar el video entero como estaba
            try:
                tl.DeleteClips(v1n + a1n, False)
                mp.AppendToTimeline([{'mediaPoolItem': mpi, 'recordFrame': inicio, 'trackIndex': 1}])
                res['restaurado'] = len(tl.GetItemListInTrack('video', 1) or [])
            except Exception as e:
                res['restaurado'] = repr(e)
result = res
'''


def _recortar_en_resolve_libre(segmentos):
    """DaVinci Resolve FREE (sin MCP): lo mismo por el Puente (CineCaptions_Pausas.lua). La orden va como json + sidecar .lua; el informe sale del registro de Resolve."""
    import time
    import archivos_seguros
    import resolve_bridge
    import sidecar_lua
    carpeta = resolve_bridge.CARPETA_COMPARTIDA
    orden = {'segs': [[round(float(a), 6), round(float(b), 6)] for a, b in segmentos]}
    ruta = carpeta / 'pausas_orden.json'
    archivos_seguros.escribir_json(ruta, orden)
    sidecar_lua.escribir_sidecar(ruta, orden)
    if resolve_bridge.modo_actual() == 'manual' and not resolve_bridge.lanzar_puente_auto():
        return {'ok': False, 'error': 'el Puente de Resolve no está activo'}
    desde = time.time()
    ok, err = resolve_bridge.ejecutar('pausas', timeout=180)
    rep = next((r for r in reversed(resolve_bridge.reportes_del_registro()) if r.get('script') == 'CineCaptions_Pausas' and (r.get('cuando') or 0) >= desde - 2), None)
    info = (rep or {}).get('pausas')
    if isinstance(info, dict):
        info['ok'] = bool(info.get('ok')) and bool(ok)
        return info
    return {'ok': bool(ok), 'error': '' if ok else (err or 'Resolve no contestó')}


def recortar_en_resolve(segmentos):
    """Rehace V1/A1 del timeline actual con esos tramos (segundos de la fuente) pegados. Devuelve el informe de Resolve: {'ok': bool, 'error'?, 'tramos', 'v1', 'a1'}."""
    import resolve_mcp
    if resolve_mcp.ruta_exe() is None:                 # v5.4.16: sin MCP = Resolve Free: por el Puente
        return _recortar_en_resolve_libre(segmentos)
    codigo = _CORTAR % {'segs': [(round(float(a), 6), round(float(b), 6)) for a, b in segmentos]}
    ok, r, err = resolve_mcp.script(codigo, timeout=120)
    if not ok or not isinstance(r, dict):
        return {'ok': False, 'error': err or 'Resolve no contestó'}
    return r
