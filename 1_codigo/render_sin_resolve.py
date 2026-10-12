# CineCaptions · By Cinema Productions
# 1_codigo/render_sin_resolve.py — GO SIN DaVinci Resolve (v5.4.47): el video con los subtítulos de Tema 4 grabados, sus sonidos y emojis, en un MP4.
"""
render_sin_resolve.py
---------------------
Pedido (2026-10-11): «¿puedes hacer que funcione sin DaVinci Resolve?» → si Resolve no está instalado, GO entrega el video con los
subtítulos ya puestos. Los estilos de Resolve son macros de Fusion (Luxe) que solo existen dentro de Resolve; aquí se DIBUJAN con
Pillow a partir del mismo plan (`tema4_planificador.cues_de` → el .guion.json), así que el texto, el tamaño y la posición de cada
palabra son los de Tema 4 en Resolve; la animación es una aproximación medida sobre `TEMA 4.mp4`: cada palabra entra con un fundido
de ~3 fotogramas en su sitio final, halo blanco suave, letras apretadas.

    renderizar(video, cues, salida=None, progreso=None, cancelado=None, emoji_arriba=True) -> {'ok', 'ruta', 'segundos', 'codec', ...}

- Imagen: PyAV decodifica cada fotograma (con la rotación del celular aplicada), se compone el texto solo en el rectángulo de cada
  palabra (numpy) y se codifica en H.264 (libx264; si no, el H.264 del sistema; si no, MPEG-4) con los mismos tiempos del original.
- Sonido: el audio original + los sonidos de cada palabra (`sfx_eventos[].sfx_archivo`, ya con su volumen) mezclados a 48 kHz → AAC.
- Emojis: el PNG de `emojis.ruta_png` encima (o debajo) de la caja del bloque, desde `emoji_ini` hasta que se va el bloque.
- El MP4 se escribe con un nombre temporal y se renombra al final: si se cancela o falla no queda un archivo a medias.
- Vertical: el diseño ocupa el ancho del video (1080×1920 = el de Resolve). Horizontal: el mismo bloque, más grande, en el tercio inferior.
"""
import os
import sys
import time
from fractions import Fraction
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import guion_captions as GC
import tema4_planificador as T

ENTRADA_S = 0.09            # fundido de cada palabra (≈3 fotogramas a 30 fps), medido en TEMA 4.mp4
SALIDA_S = 0.05             # el bloque se va casi de golpe (la frase siguiente lo reemplaza)
HALO = (0.14, 0.7)          # radio del halo blanco (× la letra) e intensidad (comparado con TEMA 4.mp4)
EMOJI_LADO = 150.0          # px del diseño (1080×1920)
EMOJI_HUECO = 24.0
EMOJI_ENTRADA_S = 0.14
SR = 48000                  # audio de salida
HORIZONTAL_ESCALA = 2.4     # en horizontal el bloque se agranda (el diseño es para 9:16): ~31 % del ancho, como un subtítulo
HORIZONTAL_Y = 0.78         # y de la primera línea de base en horizontal (fracción del alto): tercio inferior


class Cancelado(Exception):
    pass


# ------------------------------------------------------------------------------------------------------------------ geometría
def encaje(ancho, alto):
    """(escala, dx, dy): de las coordenadas del diseño (1080×1920, las de Resolve) a píxeles de ESTE video."""
    if alto >= ancho * 0.95:
        s = ancho / 1080.0
        return s, 0.0, (alto - 1920.0 * s) / 2.0
    s = alto / 1920.0 * HORIZONTAL_ESCALA
    centro_y = 0.576 * 1920.0                    # la primera línea de base de Tema 4 (57,6 % del alto)
    return s, (ancho - 1080.0 * s) / 2.0, HORIZONTAL_Y * alto - centro_y * s


def _sprite_texto(texto, em):
    """(rgb float32 HxWx3, alfa float32 HxWx1, x_inicio, linea_de_base, ancho_tinta) de una palabra blanca con su halo."""
    f = GC._fuente(T.FUENTE, em)
    if f is None:
        return None
    anchos = [f.getlength(ch) * T.ESPACIADO for ch in texto]
    total = sum(anchos)
    asc, desc = f.getmetrics()
    pad = int(em * 0.5) + 4
    w, h = int(total + 2 * pad + em * 0.25) + 1, int(asc + desc + 2 * pad) + 1
    img = Image.new('RGBA', (w, h), (255, 255, 255, 0))
    d = ImageDraw.Draw(img)
    x, base = float(pad), float(pad + asc)
    for ch, a in zip(texto, anchos):
        d.text((x, base), ch, font=f, fill=(255, 255, 255, 255), anchor='ls')
        x += a
    alfa = img.getchannel('A')
    halo = alfa.filter(ImageFilter.GaussianBlur(max(1.5, em * HALO[0]))).point(lambda v: int(v * HALO[1]))
    capa = Image.new('RGBA', img.size, (255, 255, 255, 0))
    capa.putalpha(halo)
    capa.alpha_composite(img)
    arr = np.asarray(capa, dtype=np.float32)
    return arr[..., :3].copy(), arr[..., 3:4] / 255.0, float(pad), base, total


def _sprite_emoji(ruta, lado):
    try:
        with Image.open(ruta) as im:
            im = im.convert('RGBA')
            im.thumbnail((int(lado), int(lado)), Image.LANCZOS)
            arr = np.asarray(im, dtype=np.float32)
        return arr[..., :3].copy(), arr[..., 3:4] / 255.0
    except Exception:
        return None


def preparar(cues, ancho, alto, emoji_arriba=True):
    """Todo lo que se dibuja, ya rasterizado: [{'rgb','a','x','y','t0','t1','entrada'}] (x, y = esquina superior izquierda)."""
    s, dx, dy = encaje(ancho, alto)
    capas = []
    for cue in cues or []:
        ini, fin = float(cue.get('start') or 0.0), float(cue.get('end') or 0.0)
        if fin <= ini:
            continue
        for r in cue.get('runs') or []:
            texto = str(r.get('texto') or '').strip()
            if not texto:
                continue
            em = T.EM_BASE * float(r.get('zoom', 1.0)) * s
            sp = _sprite_texto(texto, em)
            if sp is None:
                continue
            rgb, a, x_ini, base, total = sp
            cx = dx + float(r['x']) * 1080.0 * s
            cy = dy + float(r['y']) * 1920.0 * s
            izq = cx - total / 2.0 - x_ini
            arriba = cy + T.CENTRO_CAP * em - base
            capas.append({'rgb': rgb, 'a': a, 'x': int(round(izq)), 'y': int(round(arriba)),
                          't0': max(ini, float(r.get('t', ini))), 't1': fin, 'entrada': ENTRADA_S})
        if cue.get('emoji'):
            try:
                import emojis
                ruta = emojis.ruta_png(cue['emoji'])
            except Exception:
                ruta = None
            lado = EMOJI_LADO * s
            sp = _sprite_emoji(ruta, lado) if ruta else None
            caja = cue.get('caja')
            if sp is not None and isinstance(caja, (list, tuple)) and len(caja) == 2:
                rgb, a = sp
                hh, ww = a.shape[:2]
                if emoji_arriba:
                    cy = dy + float(caja[0]) * 1920.0 * s - EMOJI_HUECO * s - hh / 2.0
                else:
                    cy = dy + float(caja[1]) * 1920.0 * s + EMOJI_HUECO * s + hh / 2.0
                cx = dx + 540.0 * s
                capas.append({'rgb': rgb, 'a': a, 'x': int(round(cx - ww / 2.0)), 'y': int(round(cy - hh / 2.0)),
                              't0': max(ini, float(cue.get('emoji_ini') or ini)), 't1': fin, 'entrada': EMOJI_ENTRADA_S})
    capas.sort(key=lambda c: c['t0'])
    return capas


def _fuerza(c, t):
    """0..1: cuánto se ve la capa en el instante t (fundido de entrada suave y salida corta)."""
    if t < c['t0'] or t >= c['t1']:
        return 0.0
    k = min(1.0, (t - c['t0']) / c['entrada']) if c['entrada'] > 0 else 1.0
    k = k * k * (3.0 - 2.0 * k)
    if SALIDA_S > 0:
        k *= min(1.0, (c['t1'] - t) / SALIDA_S)
    return k


def componer(arr, capas, t):
    """Dibuja sobre `arr` (HxWx3 uint8, se modifica) las capas visibles en t. Devuelve cuántas se dibujaron."""
    alto, ancho = arr.shape[:2]
    n = 0
    for c in capas:
        if c['t0'] > t:
            break
        k = _fuerza(c, t)
        if k <= 0.0:
            continue
        h, w = c['a'].shape[:2]
        x0, y0 = max(0, c['x']), max(0, c['y'])
        x1, y1 = min(ancho, c['x'] + w), min(alto, c['y'] + h)
        if x1 <= x0 or y1 <= y0:
            continue
        sx, sy = x0 - c['x'], y0 - c['y']
        a = c['a'][sy:sy + (y1 - y0), sx:sx + (x1 - x0)] * k
        reg = arr[y0:y1, x0:x1].astype(np.float32)
        reg += (c['rgb'][sy:sy + (y1 - y0), sx:sx + (x1 - x0)] - reg) * a
        arr[y0:y1, x0:x1] = np.clip(reg + 0.5, 0, 255).astype(np.uint8)
        n += 1
    return n


# ------------------------------------------------------------------------------------------------------------------ sonido
def _leer_audio(ruta):
    """Audio de un archivo como float32 (2, N) a 48 kHz; None si no tiene."""
    import av
    try:
        cont = av.open(str(ruta))
    except Exception:
        return None
    try:
        if not cont.streams.audio:
            return None
        rs = av.AudioResampler(format='fltp', layout='stereo', rate=SR)
        trozos = []
        for fr in cont.decode(cont.streams.audio[0]):
            for o in rs.resample(fr):
                trozos.append(o.to_ndarray())
        for o in rs.resample(None):
            trozos.append(o.to_ndarray())
        if not trozos:
            return None
        return np.concatenate(trozos, axis=1).astype(np.float32)
    except Exception:
        return None
    finally:
        cont.close()


def mezclar_audio(video, cues, duracion):
    """El audio original + los sonidos de cada palabra, (2, N) float32 a 48 kHz, o None si no hay nada que sonar."""
    base = _leer_audio(video)
    largo = int(max(duracion, (base.shape[1] / SR) if base is not None else 0.0) * SR) + 1
    eventos = [(float(ev.get('t') or 0.0), ev.get('sfx_archivo') or ev.get('sfx_original'))
               for cue in cues or [] for ev in (cue.get('sfx_eventos') or []) if ev.get('sfx_archivo') or ev.get('sfx_original')]
    if base is None and not eventos:
        return None
    mezcla = np.zeros((2, largo), dtype=np.float32)
    if base is not None:
        mezcla[:, :min(largo, base.shape[1])] += base[:, :largo]
    cache = {}
    for t, ruta in eventos:
        if not ruta or not Path(ruta).is_file():
            continue
        if ruta not in cache:
            cache[ruta] = _leer_audio(ruta)
        s = cache[ruta]
        i = int(round(t * SR))
        if s is None or i >= largo:
            continue
        n = min(s.shape[1], largo - i)
        mezcla[:, i:i + n] += s[:, :n]
    pico = float(np.max(np.abs(mezcla))) if mezcla.size else 0.0
    if pico > 1.0:                               # sin recortes: se baja todo lo justo
        mezcla /= pico
    return mezcla


# ------------------------------------------------------------------------------------------------------------------ video
def _abrir_codificador(out, fps, ancho, alto):
    """El primer H.264 que funcione en este equipo (libx264 viene con PyAV), o MPEG-4."""
    import av
    for nombre, opciones in (('libx264', {'crf': '18', 'preset': 'veryfast'}),
                             ('h264_videotoolbox', {}), ('h264_mf', {}), ('mpeg4', {})):
        try:
            av.codec.Codec(nombre, 'w')
        except Exception:
            continue
        try:
            vs = out.add_stream(nombre, rate=fps)
            vs.width, vs.height = ancho, alto
            vs.pix_fmt = 'yuv420p'
            if opciones:
                vs.options = opciones
            else:
                vs.bit_rate = 14_000_000
            return vs, nombre
        except Exception:
            continue
    raise RuntimeError('no hay ningún codificador de video H.264 ni MPEG-4 en este equipo')


def ruta_de_salida(video):
    """«<video> (CineCaptions).mp4» junto al original (si ya existe: «… 2», «… 3»…)."""
    video = Path(video)
    for n in range(1, 200):
        sufijo = ' (CineCaptions)' if n == 1 else f' (CineCaptions {n})'
        cand = video.with_name(video.stem + sufijo + '.mp4')
        if not cand.exists():
            return cand
    return video.with_name(video.stem + f' (CineCaptions {int(time.time())}).mp4')


def _carpeta_escribible(destino):
    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        prueba = destino.parent / f'.cinecaptions_prueba_{os.getpid()}'
        prueba.write_bytes(b'')
        prueba.unlink()
        return True
    except OSError:
        return False


def renderizar(video, cues, salida=None, progreso=None, cancelado=None, emoji_arriba=True):
    """El MP4 con los subtítulos grabados. `progreso(fraccion, texto)` y `cancelado()` se llaman desde ESTE hilo (correr fuera de la interfaz)."""
    import av
    t_inicio = time.time()
    video = Path(video)
    destino = Path(salida) if salida else ruta_de_salida(video)
    if not _carpeta_escribible(destino):              # carpeta de solo lectura (un USB protegido, una carpeta del sistema): a Videos/Movies
        casa = Path.home() / ('Movies' if sys.platform == 'darwin' else 'Videos')
        destino = ruta_de_salida(casa / 'CineCaptions' / video.name)
        destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_name(f'.~{destino.stem}.{os.getpid()}.mp4')

    def avisar(f, texto=''):
        if progreso:
            try:
                progreso(max(0.0, min(1.0, f)), texto)
            except Exception:
                pass

    def mirar_cancelar():
        if cancelado and cancelado():
            raise Cancelado()

    entrada = av.open(str(video))
    out = None
    try:
        if not entrada.streams.video:
            raise RuntimeError('el archivo no tiene imagen (¿es solo audio?)')
        vin = entrada.streams.video[0]
        vin.thread_type = 'AUTO'
        tb = vin.time_base
        inicio_pts = vin.start_time or 0
        fps = vin.average_rate or vin.guessed_rate or Fraction(30, 1)
        dur = float(vin.duration * tb) if vin.duration else (float(entrada.duration) / 1e6 if entrada.duration else 0.0)
        total_cuadros = int(vin.frames or 0) or max(1, int(dur * float(fps)))

        avisar(0.0, 'Preparando el sonido…')
        mezcla = mezclar_audio(video, cues, dur)
        mirar_cancelar()

        out = av.open(str(temporal), 'w', format='mp4', options={'movflags': '+faststart'})
        vs = None
        nombre_codec = ''
        capas = None
        aus = None
        if mezcla is not None:
            try:
                aus = out.add_stream('aac', rate=SR, layout='stereo')
            except TypeError:
                aus = out.add_stream('aac', rate=SR)
            aus.bit_rate = 192_000
        pos_audio = 0
        bloque_audio = 1024

        def audio_hasta(seg=None):
            """Codifica el audio hasta `seg` segundos (None = todo lo que queda, con el último trozo rellenado de silencio)."""
            nonlocal pos_audio
            if aus is None:
                return
            fin = mezcla.shape[1] if seg is None else min(mezcla.shape[1], int(seg * SR))
            while pos_audio + bloque_audio <= fin or (seg is None and pos_audio < fin):
                trozo = mezcla[:, pos_audio:pos_audio + bloque_audio]
                if trozo.shape[1] < bloque_audio:
                    trozo = np.pad(trozo, ((0, 0), (0, bloque_audio - trozo.shape[1])))
                af = av.AudioFrame.from_ndarray(np.ascontiguousarray(trozo), format='fltp', layout='stereo')
                af.sample_rate = SR
                af.pts = pos_audio
                af.time_base = Fraction(1, SR)
                for p in aus.encode(af):
                    out.mux(p)
                pos_audio += bloque_audio

        avisar(0.02, 'Grabando los subtítulos en el video…')
        n = 0
        ultimo_aviso = 0.0
        for fr in entrada.decode(vin):
            mirar_cancelar()
            rot = int(getattr(fr, 'rotation', 0) or 0)
            arr = fr.to_ndarray(format='rgb24')
            if rot % 360:
                arr = np.ascontiguousarray(np.rot90(arr, k=int(round(rot / 90.0)) % 4))
            if arr.shape[0] % 2 or arr.shape[1] % 2:          # yuv420p pide lados pares
                arr = np.ascontiguousarray(arr[:arr.shape[0] // 2 * 2, :arr.shape[1] // 2 * 2])
            alto, ancho = arr.shape[:2]
            if vs is None:
                vs, nombre_codec = _abrir_codificador(out, fps, ancho, alto)
                try:
                    vs.codec_context.time_base = tb
                except Exception:
                    pass
                capas = preparar(cues, ancho, alto, emoji_arriba=emoji_arriba)
            pts = (fr.pts - inicio_pts) if fr.pts is not None else None
            t = float(pts * tb) if pts is not None else n / float(fps)
            componer(arr, capas, t)
            nf = av.VideoFrame.from_ndarray(arr, format='rgb24')
            if pts is not None:
                nf.pts = pts
                nf.time_base = tb
            for p in vs.encode(nf):
                out.mux(p)
            audio_hasta(t + 0.5)
            n += 1
            ahora = time.time()
            if ahora - ultimo_aviso > 0.25:
                ultimo_aviso = ahora
                avisar(0.02 + 0.96 * n / total_cuadros, f'Grabando los subtítulos en el video… {min(99, int(100 * n / total_cuadros))} %')
        if vs is None:
            raise RuntimeError('no pude leer ningún fotograma del video')
        for p in vs.encode(None):
            out.mux(p)
        audio_hasta(None)
        if aus is not None:
            for p in aus.encode(None):
                out.mux(p)
        out.close()
        out = None
        entrada.close()
        os.replace(temporal, destino)
        avisar(1.0, 'Listo')
        return {'ok': True, 'ruta': str(destino), 'segundos': round(time.time() - t_inicio, 1), 'codec': nombre_codec,
                'cuadros': n, 'con_audio': mezcla is not None}
    except Cancelado:
        return {'ok': False, 'cancelado': True, 'ruta': None}
    finally:
        for c in (out, entrada):
            try:
                if c is not None:
                    c.close()
            except Exception:
                pass
        try:
            if temporal.exists():
                temporal.unlink()
        except OSError:
            pass


def mostrar_en_carpeta(ruta):
    """Abre la carpeta con el MP4 seleccionado (Explorador / Finder). Llamar desde un hilo (lanza un proceso)."""
    import subprocess
    import sys
    try:
        if sys.platform.startswith('win'):
            subprocess.Popen(['explorer', '/select,', str(ruta)], creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', '-R', str(ruta)])
        else:
            subprocess.Popen(['xdg-open', str(Path(ruta).parent)])
    except Exception:
        pass
