# CineCaptions · By Cinema Productions
# 1_codigo/banco_pruebas.py — banco de pruebas: timeline temporal con fondo liso + audio, render en Resolve y comparación cuadro a cuadro con un video de referencia.
"""
banco_pruebas.py  (v5.9)
------------------------
Para comprobar que unos subtítulos «se ven como la referencia» sin tocar tu timeline:

  1. preparar(): crea en Resolve un timeline temporal «zz_BANCO» con un fondo liso (un video generado aquí) y el audio de tu video, y lo pone como el actual
     (el timeline que tenías se restaura al limpiar()).
  2. (tú o el programa colocan los subtítulos en ese timeline: GO, Generar, la herramienta MCP…)
  3. renderizar(): exporta el timeline a un MP4 (por la cola de render de Resolve, no por stills) y espera a que termine.
  4. cuadros() / hoja() / lado_a_lado(): saca cuadros del render y de la referencia y los junta para mirarlos; medir_texto() mide dónde cae el texto
     (sobre un fondo liso es exacto: todo lo que no es fondo es subtítulo).
  5. limpiar(): borra el timeline y el bin temporales y vuelve al timeline de antes.

Todo lo que habla con Resolve va por resolve_mcp.script (nunca desde el hilo de la interfaz).
"""
import json
import os
import time
from pathlib import Path

import resolve_mcp

CARPETA = Path.home() / 'DaVinciSubtitles' / 'banco'
NOMBRE = NOMBRE_TL = 'zz_BANCO'
ESTADO = CARPETA / 'estado.json'


# ------------------------------------------------------------------------------------------------------------------ fondo liso
def crear_fondo(ruta=None, color=(70, 70, 70), frames=718, fps=30, ancho=1080, alto=1920):
    """Un MP4 de un solo color (rápido: unos segundos). Devuelve la ruta."""
    import av
    import numpy as np
    CARPETA.mkdir(parents=True, exist_ok=True)
    ruta = Path(ruta or CARPETA / f'fondo_{color[0]}_{frames}.mp4')
    if ruta.exists():
        return str(ruta)
    c = av.open(str(ruta), 'w')
    s = c.add_stream('libx264', rate=fps)
    s.width, s.height, s.pix_fmt = ancho, alto, 'yuv420p'
    s.options = {'crf': '18', 'preset': 'ultrafast'}
    fr = av.VideoFrame.from_ndarray(np.full((alto, ancho, 3), color, np.uint8), format='rgb24')
    for _ in range(int(frames)):
        fr.pts = None
        for p in s.encode(fr):
            c.mux(p)
    for p in s.encode():
        c.mux(p)
    c.close()
    return str(ruta)


# ------------------------------------------------------------------------------------------------------------------ Resolve
_PREPARAR = r'''
NOMBRE = %(nombre)r
mp = project.GetMediaPool()
previo = project.GetCurrentTimeline()
res = {'previo': previo.GetName() if previo else None, 'proyecto': project.GetName()}
# ya hay uno de una vez anterior: fuera
for i in range(1, int(project.GetTimelineCount() or 0) + 1):
    t = project.GetTimelineByIndex(i)
    if t and t.GetName() == NOMBRE:
        if previo and previo.GetName() == NOMBRE:
            for j in range(1, int(project.GetTimelineCount() or 0) + 1):
                o = project.GetTimelineByIndex(j)
                if o and o.GetName() != NOMBRE:
                    project.SetCurrentTimeline(o); break
        mp.DeleteTimelines([t])
        break
raiz = mp.GetRootFolder()
for c in (raiz.GetSubFolderList() or []):
    if c.GetName() == NOMBRE:
        mp.DeleteFolders([c]); break
# packs que se acaban de reconstruir: su bin del proyecto es de la versión vieja
renovar = %(renovar)r
for c in list(raiz.GetSubFolderList() or []):
    if any(c.GetName().startswith('RCS · ' + n) for n in renovar):
        mp.DeleteFolders([c])
carpeta = mp.AddSubFolder(raiz, NOMBRE)
mp.SetCurrentFolder(carpeta)
fondo = mp.ImportMedia([%(fondo)r])
audio = mp.ImportMedia([%(audio)r]) if %(audio)r else None
tl = mp.CreateEmptyTimeline(NOMBRE)
res['timeline'] = bool(tl)
if tl:
    # sin «useCustomSettings» el timeline usa los ajustes del PROYECTO (p. ej. 1920x1080 a 29,97) y las demás claves se ignoran sin avisar
    try: tl.SetSetting('useCustomSettings', '1')
    except Exception: pass
    for k, v in (('timelineResolutionWidth', %(ancho)r), ('timelineResolutionHeight', %(alto)r), ('timelineFrameRate', %(fps)r), ('timelineOutputResolutionWidth', %(ancho)r), ('timelineOutputResolutionHeight', %(alto)r)):
        try: tl.SetSetting(k, v)
        except Exception: pass
    project.SetCurrentTimeline(tl)
    if fondo:
        mp.AppendToTimeline([{'mediaPoolItem': fondo[0], 'mediaType': 1}])
    if audio:
        mp.AppendToTimeline([{'mediaPoolItem': audio[0], 'mediaType': 2}])
    res['pistas'] = {t: tl.GetTrackCount(t) for t in ('video', 'audio')}
    res['inicio'] = tl.GetStartFrame(); res['fin'] = tl.GetEndFrame()
result = res
'''

_LIMPIAR = r'''
NOMBRE = %(nombre)r
previo = %(previo)r
mp = project.GetMediaPool()
res = {}
if previo:
    for i in range(1, int(project.GetTimelineCount() or 0) + 1):
        t = project.GetTimelineByIndex(i)
        if t and t.GetName() == previo:
            project.SetCurrentTimeline(t); break
tls = [project.GetTimelineByIndex(i) for i in range(1, int(project.GetTimelineCount() or 0) + 1)]
borrar = [t for t in tls if t and t.GetName() == NOMBRE]
res['timeline'] = bool(mp.DeleteTimelines(borrar)) if borrar else None
raiz = mp.GetRootFolder()
cs = [c for c in (raiz.GetSubFolderList() or []) if c.GetName() == NOMBRE]
if cs:
    mp.SetCurrentFolder(raiz)
    res['bin'] = bool(mp.DeleteFolders(cs))
res['actual'] = project.GetCurrentTimeline().GetName() if project.GetCurrentTimeline() else None
result = res
'''

_RENDER = r'''
import os, glob
destino = %(destino)r
nombre = %(nombre)r
tl = project.GetCurrentTimeline()
res = {'timeline': tl.GetName()}
# solo se borran los trabajos DEL BANCO (los que van a su carpeta): la cola de render del usuario no se toca
for j in (project.GetRenderJobList() or []):
    if os.path.normcase(os.path.normpath(str(j.get('TargetDir') or ''))) == os.path.normcase(os.path.normpath(destino)):
        project.DeleteRenderJob(j['JobId'])
res['preset'] = bool(project.LoadRenderPreset('H.264 Master'))
ajustes = {'SelectAllFrames': True, 'TargetDir': destino, 'CustomName': nombre}
# el preajuste trae 1920x1080 a 29,97: se pide la resolución y los fps del PROPIO timeline (si no, un timeline vertical sale con barras a los lados)
try:
    ajustes['FormatWidth'] = int(float(tl.GetSetting('timelineResolutionWidth')))
    ajustes['FormatHeight'] = int(float(tl.GetSetting('timelineResolutionHeight')))
    ajustes['FrameRate'] = float(tl.GetSetting('timelineFrameRate'))
except Exception:
    pass
res['ajustes'] = bool(project.SetRenderSettings(ajustes))
for ruta in glob.glob(os.path.join(destino, nombre + '.*')):
    try: os.remove(ruta)
    except Exception: pass
job = project.AddRenderJob()
res['job'] = job
if job:
    res['inicio'] = bool(project.StartRendering(job))
result = res
'''

_BORRAR_TRABAJOS = r'''
import os
destino = %(destino)r
for j in (project.GetRenderJobList() or []):
    if os.path.normcase(os.path.normpath(str(j.get('TargetDir') or ''))) == os.path.normcase(os.path.normpath(destino)):
        project.DeleteRenderJob(j['JobId'])
result = True
'''

_ESTADO_RENDER = r'''
job = %(job)r
en_curso = bool(project.IsRenderingInProgress())
st = project.GetRenderJobStatus(job) or {}
result = {'en_curso': en_curso, 'estado': st}
'''


def _script(codigo, timeout=60):
    ok, r, err = resolve_mcp.script(codigo, timeout=timeout)
    if not ok:
        raise RuntimeError(f'Resolve: {err}')
    return r


def preparar(audio=None, color=(70, 70, 70), frames=718, fps=30, ancho=1080, alto=1920, fondo=None, renovar=('Referencia',)):
    """Crea el timeline temporal y lo deja como el actual. Devuelve lo que informa Resolve. Guarda el timeline previo para limpiar()."""
    CARPETA.mkdir(parents=True, exist_ok=True)
    fondo = fondo or crear_fondo(color=color, frames=frames, fps=fps, ancho=ancho, alto=alto)
    codigo = _PREPARAR % {'nombre': NOMBRE, 'fondo': str(fondo), 'audio': str(audio) if audio else '', 'ancho': str(ancho), 'alto': str(alto), 'fps': str(fps), 'renovar': tuple(renovar)}
    r = _script(codigo, 60)
    if isinstance(r, dict) and r.get('previo') != NOMBRE:
        ESTADO.write_text(json.dumps(r, ensure_ascii=False), encoding='utf-8')
    return r


def limpiar():
    previo = None
    try:
        previo = json.loads(ESTADO.read_text(encoding='utf-8')).get('previo')
    except Exception:
        pass
    r = _script(_LIMPIAR % {'nombre': NOMBRE, 'previo': previo}, 40)
    return r


def renderizar(nombre='banco', esperar=True, tope_s=300, **_):
    """Renderiza el timeline actual a CARPETA/nombre.mov con el preajuste «H.264 Master» (cola de render de Resolve; a resolución del timeline). Devuelve la ruta (o None)."""
    CARPETA.mkdir(parents=True, exist_ok=True)
    destino = str(CARPETA)
    r = _script(_RENDER % {'destino': destino, 'nombre': nombre}, 40)
    if not isinstance(r, dict) or not r.get('job'):
        raise RuntimeError(f'Resolve no creó el trabajo de render: {r}')
    if not esperar:
        return r
    t0 = time.time()
    time.sleep(1.5)
    while time.time() - t0 < tope_s:
        e = _script(_ESTADO_RENDER % {'job': r['job']}, 20)
        st = (e or {}).get('estado') or {}
        if str(st.get('JobStatus', '')).lower() in ('complete', 'failed', 'cancelled') or (not e.get('en_curso') and st.get('CompletionPercentage') == 100):
            break
        time.sleep(1.0)
    for _ in range(20):
        for ruta in sorted(CARPETA.glob(nombre + '.*')):
            if ruta.suffix.lower() in ('.mov', '.mp4') and ruta.stat().st_size > 1000:
                time.sleep(0.5)
                _script(_BORRAR_TRABAJOS % {'destino': destino}, 20)
                return str(ruta)
        time.sleep(0.5)
    return None


# ------------------------------------------------------------------------------------------------------------------ cuadros y comparación
def cuadros(ruta, indices, ancho=540, alto=960):
    """{indice: ndarray RGB alto×ancho×3} de esos cuadros (decodifica una vez)."""
    import av
    wanted = sorted(set(int(i) for i in indices))
    salida = {}
    c = av.open(str(ruta))
    for i, fr in enumerate(c.decode(video=0)):
        if i in wanted:
            salida[i] = fr.reformat(width=ancho, height=alto, format='rgb24').to_ndarray()
            if len(salida) == len(wanted):
                break
    c.close()
    return salida


def lado_a_lado(ruta_a, ruta_b, indices, salida, recorte=(0.15, 0.85), ancho=540, rotulos=('referencia', 'mío')):
    """Una imagen: por cada cuadro, la referencia a la izquierda y el render a la derecha (solo la franja vertical `recorte`)."""
    from PIL import Image, ImageDraw
    A, B = cuadros(ruta_a, indices, ancho, int(ancho * 16 / 9)), cuadros(ruta_b, indices, ancho, int(ancho * 16 / 9))
    alto = int(ancho * 16 / 9)
    y0, y1 = int(alto * recorte[0]), int(alto * recorte[1])
    h = y1 - y0
    hoja = Image.new('RGB', (ancho * 2, h * len(indices)))
    for k, i in enumerate(indices):
        for col, D in enumerate((A, B)):
            if i in D:
                im = Image.fromarray(D[i][y0:y1])
                d = ImageDraw.Draw(im)
                d.rectangle((0, 0, 130, 14), fill=(0, 0, 0))
                d.text((3, 2), f'{rotulos[col]} f{i} {i / 30:.2f}s', fill=(255, 255, 0))
                hoja.paste(im, (col * ancho, k * h))
    hoja.save(salida, quality=88)
    return salida


def hoja(ruta, tiempos, salida, ancho=270, recorte=(0.12, 0.88), columnas=4, fps=30, aspecto=16 / 9):
    """Una imagen con los cuadros de `ruta` en esos instantes (segundos), en una rejilla de `columnas`; cada celda lleva su hora. `aspecto` = alto/ancho del cuadro (16/9 vertical; 9/16 horizontal)."""
    from PIL import Image, ImageDraw
    indices = [int(round(t * fps)) for t in tiempos]
    D = cuadros(ruta, indices, ancho, int(ancho * aspecto))
    alto = int(ancho * aspecto)
    y0, y1 = int(alto * recorte[0]), int(alto * recorte[1])
    h = y1 - y0
    filas = (len(indices) + columnas - 1) // columnas
    img = Image.new('RGB', (ancho * min(columnas, len(indices)), h * filas), (20, 20, 20))
    for k, (t, i) in enumerate(zip(tiempos, indices)):
        if i not in D:
            continue
        celda = Image.fromarray(D[i][y0:y1])
        ImageDraw.Draw(celda).text((3, 2), f'{t:.2f}s', fill=(255, 255, 0))
        img.paste(celda, ((k % columnas) * ancho, (k // columnas) * h))
    Path(salida).parent.mkdir(parents=True, exist_ok=True)
    img.save(salida, quality=88)
    return str(salida)


def medir_texto(ruta, indices, fondo=(70, 70, 70), umbral=28, ancho=540, aspecto=16 / 9):
    """Sobre el fondo liso: por cuadro, las filas/columnas ocupadas por texto → [{'f', 'cajas': [(y0, y1, x0, x1)…]}] en fracciones del cuadro.
    Agrupa las filas con texto en «líneas» separadas por huecos de más de 6 px."""
    import numpy as np
    alto = int(ancho * aspecto)
    D = cuadros(ruta, indices, ancho, alto)
    fondo = np.array(fondo, dtype=np.int16)
    salida = []
    for i in indices:
        if i not in D:
            continue
        m = (np.abs(D[i].astype(np.int16) - fondo).max(axis=2) > umbral)
        filas = np.where(m.any(axis=1))[0]
        cajas = []
        if len(filas):
            grupos = np.split(filas, np.where(np.diff(filas) > 6)[0] + 1)
            for g in grupos:
                if len(g) < 3:
                    continue
                cols = np.where(m[g[0]:g[-1] + 1].any(axis=0))[0]
                cajas.append((round(g[0] / alto, 4), round(g[-1] / alto, 4), round(cols[0] / ancho, 4), round(cols[-1] / ancho, 4)))
        salida.append({'f': i, 'cajas': cajas})
    return salida


# ------------------------------------------------------------------------------------------------------------------ colocar un guion
def colocar_guion(cues, pack='Referencia', idioma='es', archivo='guion_prueba', timeout=300):
    """Escribe los datos del estilo «guion» y el manifiesto, y corre el script de Resolve sobre el timeline ACTUAL. Devuelve (ok, mensaje)."""
    import archivos_seguros
    import guion_captions
    import plantillas
    import resolve_bridge
    # «datos_»: el render borra todo lo que empiece por su nombre
    datos = guion_captions.escribir(cues, CARPETA / f'datos_{archivo}.{idioma}.guion.json', idioma)
    pl = plantillas.para_manifiesto(pack, formato_forzado='v')
    track = {'language': idioma, 'style': 'guion', 'data_path': datos, 'srt_path': '', 'fonts': {}, 'adelanto_frames': 0, 'offset_frames': None,
             'plantilla': pl.get('plantilla') if isinstance(pl, dict) and 'plantilla' in pl else pl}
    manifiesto = Path.home() / 'DaVinciSubtitles' / 'subtitles_manifest.json'
    archivos_seguros.escribir_json(manifiesto, {'project': archivo, 'tracks': [track]})
    return resolve_bridge.ejecutar('subtitulos', timeout=timeout)


def colocar_kinetic(cues, pack='Kinetic', idioma='es', archivo='kinetic_prueba', timeout=300):
    """Como colocar_guion pero para el estilo «Kinetic»: escribe sus datos y el manifiesto (style='kinetic') y corre el script de Resolve sobre el timeline ACTUAL."""
    import archivos_seguros
    import kinetic_captions
    import plantillas
    import resolve_bridge
    datos = kinetic_captions.escribir(cues, CARPETA / f'datos_{archivo}.{idioma}.kinetic.json', idioma)
    pl = plantillas.para_manifiesto(pack, formato_forzado='v')
    track = {'language': idioma, 'style': 'kinetic', 'data_path': datos, 'srt_path': '', 'fonts': {}, 'adelanto_frames': 0, 'offset_frames': None,
             'plantilla': pl.get('plantilla') if isinstance(pl, dict) and 'plantilla' in pl else pl}
    manifiesto = Path.home() / 'DaVinciSubtitles' / 'subtitles_manifest.json'
    archivos_seguros.escribir_json(manifiesto, {'project': archivo, 'tracks': [track]})
    return resolve_bridge.ejecutar('subtitulos', timeout=timeout)


def colocar_viral(cues, pack='VIRAL', idioma='es', archivo='viral_prueba', timeout=300, formato='v'):
    """Como colocar_kinetic pero para el estilo «VIRAL» (mismo colocador de Resolve, otros clips: «v fina»…): escribe los datos y el manifiesto y corre el script sobre el timeline ACTUAL."""
    import archivos_seguros
    import kinetic_captions
    import plantillas
    import resolve_bridge
    datos = kinetic_captions.escribir(cues, CARPETA / f'datos_{archivo}.{idioma}.kinetic.json', idioma)
    pl = plantillas.para_manifiesto(pack, formato_forzado=formato)
    clip_prueba = next((r['k'] for c in cues for r in (c.get('runs') or []) if r.get('k')), 'v fina')
    track = {'language': idioma, 'style': 'kinetic', 'clip_prueba': clip_prueba, 'data_path': datos, 'srt_path': '', 'fonts': {}, 'adelanto_frames': 0, 'offset_frames': None,
             'plantilla': pl.get('plantilla') if isinstance(pl, dict) and 'plantilla' in pl else pl}
    manifiesto = Path.home() / 'DaVinciSubtitles' / 'subtitles_manifest.json'
    archivos_seguros.escribir_json(manifiesto, {'project': archivo, 'tracks': [track]})
    return resolve_bridge.ejecutar('subtitulos', timeout=timeout)
