# CineCaptions · By Cinema Productions
# 1_codigo/kit_neon_mp4.py — v5.5.16: el Tema 1 neón SIN DaVinci Resolve (GO «Video MP4»): los MISMOS clips que la Edición PRO pone en Resolve
# (KitNeon de Remotion, uno por caption y uno por motion, en caché) compuestos por capas —como las pistas PRO de Resolve— sobre la placa del kit
# (con la PRO: cámara, punch-ins, pantallas divididas, desenfoques) o sobre el video, con su audio, los sonidos de los captions y los de los motions.
"""
    renderizar(video, escena, plan=None, cues=None, salida=None, progreso=None, cancelado=None) -> {'ok', 'ruta', 'segundos', ...}

escena = los captions neón de GO (kit_neon.escena_captions); plan = el plan de la Edición PRO del Tema 1 (con 'kitneon_motions'); sin plan o con
un plan «ligero» = solo captions (exactamente los mismos clips de caption que con la PRO, sin los motions). Solo vertical: con un video apaisado
lanza NoVertical y GO usa el render de siempre (render_sin_resolve).
"""
import hashlib
import random
import threading
import time
from fractions import Fraction
from pathlib import Path

import numpy as np

W, H = 1080, 1920
# el orden de las pistas PRO de Resolve, de abajo arriba (colocar_pro.ORDEN + PRO-ICONOS encima de los captions)
ORDEN = {'fondo': 0, 'velo': 1, 'detras': 2, 'delante': 3, 'subs': 4, 'subs2': 5, 'iconos': 6}


class NoVertical(Exception):
    pass


def _cubrir(img, ancho, alto):
    """El fotograma escalado para LLENAR ancho × alto (recortando lo que sobra), como la placa."""
    from PIL import Image
    w, h = img.size
    s = max(ancho / w, alto / h)
    nw, nh = max(ancho, int(round(w * s))), max(alto, int(round(h * s)))
    img = img.resize((nw, nh), Image.LANCZOS)
    x0, y0 = (nw - ancho) // 2, (nh - alto) // 2
    return img.crop((x0, y0, x0 + ancho, y0 + alto))


def _mezclar(arr, a):
    """`a` (RGBA uint8, alfa sin premultiplicar) encima de `arr` (RGB uint8, se modifica), solo en el rectángulo donde `a` tiene algo
    (los captions ocupan una franja: mezclar la imagen entera en coma flotante costaba ~200 ms por fotograma)."""
    al = a[..., 3]
    filas = np.flatnonzero(al.max(axis=1))
    if not len(filas):
        return
    y0, y1 = int(filas[0]), int(filas[-1]) + 1
    cols = np.flatnonzero(al[y0:y1].max(axis=0))
    x0, x1 = int(cols[0]), int(cols[-1]) + 1
    aa = al[y0:y1, x0:x1, None].astype(np.uint16)
    sub = arr[y0:y1, x0:x1].astype(np.uint16)
    arr[y0:y1, x0:x1] = ((a[y0:y1, x0:x1, :3].astype(np.uint16) * aa + sub * (255 - aa) + 127) // 255).astype(np.uint8)


class _Clip:
    """Un clip ProRes 4444 con alfa leído en orden: `en(t_local)` devuelve su fotograma RGBA uint8 o None."""

    def __init__(self, ruta, ini, fin, z, fps):
        self.ruta, self.ini, self.fin, self.z, self.fps = ruta, ini, fin, z, fps
        self.c = self.it = None
        self.k = -1
        self.ultimo = None

    def en(self, t):
        import av
        if self.c is None:
            self.c = av.open(str(self.ruta))
            st = self.c.streams.video[0]
            st.thread_type = 'AUTO'
            self.it = self.c.decode(st)
        objetivo = int(round((t - self.ini) * self.fps))
        while self.k < objetivo:
            try:
                fr = next(self.it)
            except StopIteration:
                break
            self.k += 1
            if self.k >= objetivo:
                if fr.width != W or fr.height != H:
                    fr = fr.reformat(width=W, height=H)
                self.ultimo = fr.to_ndarray(format='rgba')
        return self.ultimo

    def cerrar(self):
        try:
            if self.c is not None:
                self.c.close()
        except Exception:
            pass
        self.c = None


def renderizar(video, escena, plan=None, cues=None, salida=None, progreso=None, cancelado=None):
    import av
    import edicion_pro as EP
    import edicion_pro_remotion as RM
    import kit_neon as KN
    import kit_neon_motions as KM
    import render_sin_resolve as RSR
    t_inicio = time.time()
    video = Path(video)

    def avisar(f, texto=''):
        if progreso:
            try:
                progreso(max(0.0, min(1.0, f)), texto)
            except Exception:
                pass

    def mirar_cancelar():
        if cancelado and cancelado():
            raise RSR.Cancelado()

    vw, vh, dur, fps_f = EP.medir(str(video))
    if vw and vh and vw > vh:
        raise NoVertical('el Tema 1 neón es vertical')
    dur = float(dur or 0.0)
    fps = Fraction(float(fps_f or 30)).limit_denominator(1001)
    fps_f = float(fps)
    con_pro = bool(plan and plan.get('tema') == 'neon' and not plan.get('ligero') and plan.get('kitneon_motions'))
    mot = list(plan.get('kitneon_motions') or []) if con_pro else []
    caps = KM.ajustar_captions(list(escena or []), mot) if mot else list(escena or [])
    piezas = (KM.piezas(mot) if mot else []) + KN.piezas(caps)
    if con_pro and 'pildora' in ((plan.get('opciones') or {}).get('_neon_extras') or []):
        try:                                             # v5.5.17: «Píldora bajo captions» del menú lateral, también sin Resolve (clips de Remotion)
            import edicion_pro_temas as TM
            extra = TM.piezas({}, str(video), plan.get('idioma') or 'es', W, H, fps_f, [], dict(plan, piezas=list(piezas)), maximo=3,
                              bloques=KN.bloques_pro(caps))
            piezas += [dict(p, capa='iconos') for p in extra if p.get('remotion') and p.get('pieza') != 'velo_caption']
        except Exception:
            pass
    if not piezas:
        raise RuntimeError('no hay captions neón que grabar')
    total = max(dur, max(p['fin'] for p in piezas))
    carpeta = EP.OG.ruta_larga(EP.CARPETA / hashlib.sha1(f'{video}|{W}x{H}@{fps_f}'.encode('utf-8')).hexdigest()[:10])
    carpeta.mkdir(parents=True, exist_ok=True)

    # 1) la placa (con la PRO) en otro hilo mientras Remotion anima los clips
    placa = {'ruta': None, 'f': 0.0}
    hilo_placa = None
    if con_pro:
        import kit_neon_placa as PLA
        plan_p = {'kitneon': caps, 'kitneon_motions': mot, 'duracion': dur, '_cortes': plan.get('_cortes') or [], '_neon_ajustado': True}

        def _placa():
            try:
                placa['ruta'] = PLA.para_pro(str(video), plan_p, carpeta, W, H, fps_f, progreso=lambda f: placa.update(f=float(f)))
            except Exception:
                placa['ruta'] = None
        hilo_placa = threading.Thread(target=_placa, daemon=True, name='placa-neon-mp4')
        hilo_placa.start()

    # 2) los clips (los mismos que van a Resolve: misma caché)
    trab, salidas = [], []
    for p in piezas:
        props = dict(p['valores'], _ancho=W, _alto=H, _fps=fps_f, _dur=round(max(0.6, p['fin'] - p['ini']), 3))
        sal = RM.salida_para(p['remotion'], props, carpeta)
        trab.append({'id': p['remotion'], 'props': props, 'salida': sal})
        salidas.append(sal)
    avisar(0.02, 'Animando los captions y los motions…')

    def estado_rm(texto):
        import re
        m = re.search(r'\((\d+) de (\d+)', str(texto))
        if m:
            avisar(0.03 + 0.5 * int(m.group(1)) / max(1, int(m.group(2))), 'Animando los captions y los motions…')
    hechos = RM.renderizar(trab, estado_rm)
    mirar_cancelar()
    clips = [_Clip(s, p['ini'], p['fin'], ORDEN.get(p['capa'], 3), fps_f) for p, s in zip(piezas, salidas) if hechos.get(str(s))]
    if not clips:
        raise RuntimeError('Remotion no pudo animar los captions neón')
    clips.sort(key=lambda c: (c.z, c.ini))
    if hilo_placa is not None:
        while hilo_placa.is_alive():
            mirar_cancelar()
            avisar(0.55 + 0.1 * placa['f'], 'Preparando la cámara del Tema 1…')
            hilo_placa.join(0.5)
    base_ruta = placa['ruta'] or video

    # 3) el audio: el del video + los sonidos de los captions (los de GO) + los de los motions (los de la PRO)
    avisar(0.66, 'Preparando el sonido…')
    mezcla = RSR.mezclar_audio(str(video), cues, total)
    if con_pro and mezcla is not None:
        try:
            import edicion_pro_sonido as PS
            for e in PS.disenar({'piezas': [p for p in piezas if p['pieza'] == 'neon_motion']}, fps_f, random.Random(0),
                                voz_db=PS.nivel_voz(str(video))):
                s = RSR._leer_audio(e['archivo'])
                if s is None:
                    continue
                i = int(round(float(e['ini']) / fps_f * RSR.SR))
                if i < 0 or i >= mezcla.shape[1]:
                    continue
                s = s[:, :int(float(e.get('dur') or 3.0) * RSR.SR)] * (10.0 ** (float(e.get('db') or 0.0) / 20.0))
                n = min(s.shape[1], mezcla.shape[1] - i)
                mezcla[:, i:i + n] += s[:, :n]
            pico = float(np.max(np.abs(mezcla))) if mezcla.size else 0.0
            if pico > 1.0:
                mezcla /= pico
        except Exception:
            pass

    # 4) componer: la base (placa o video), y encima cada clip activo en el orden de las pistas de Resolve
    destino = Path(salida) if salida else RSR.ruta_de_salida(video)
    if not RSR._carpeta_escribible(destino):
        import sys
        casa = Path.home() / ('Movies' if sys.platform == 'darwin' else 'Videos')
        destino = RSR.ruta_de_salida(casa / 'CineCaptions' / video.name)
        destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_name(f'.~{destino.stem}.{int(time.time())}.mp4')
    entrada = av.open(str(base_ruta))
    out = None
    try:
        vin = entrada.streams.video[0]
        vin.thread_type = 'AUTO'
        try:
            import rotacion_video as RV
            rot = RV.giro(str(base_ruta)) if base_ruta == video else 0
        except Exception:
            rot = 0
        cuadros = entrada.decode(vin)
        out = av.open(str(temporal), 'w', format='mp4', options={'movflags': '+faststart'})
        vs, codec = RSR._abrir_codificador(out, fps, W, H)
        aus = None
        if mezcla is not None:
            try:
                aus = out.add_stream('aac', rate=RSR.SR, layout='stereo')
            except TypeError:
                aus = out.add_stream('aac', rate=RSR.SR)
            aus.bit_rate = 192_000
        n_total = int(round(total * fps_f))
        negro = np.zeros((H, W, 3), dtype=np.uint8)
        pos_audio, bloque = 0, 1024

        def base_de(fr):
            """El fotograma de la base a W × H (llenando, como la placa); swscale escala (PIL tardaba ~30 ms)."""
            if rot:
                return np.asarray(_cubrir(RV.derecho_img(fr.to_image(), rot), W, H).convert('RGB'))
            if fr.width == W and fr.height == H:
                return fr.to_ndarray(format='rgb24')
            s = max(W / fr.width, H / fr.height)
            nw, nh = max(W, int(round(fr.width * s)) // 2 * 2), max(H, int(round(fr.height * s)) // 2 * 2)
            a = fr.reformat(width=nw, height=nh, format='rgb24').to_ndarray()
            x0, y0 = (nw - W) // 2, (nh - H) // 2
            return np.ascontiguousarray(a[y0:y0 + H, x0:x0 + W])

        # v5.5.17: en tres tiempos A LA VEZ: un hilo DECODIFICA en orden (la base y cada clip), varios MEZCLAN (numpy suelta el GIL) y este
        # CODIFICA en orden con el audio (antes, todo en fila: ~1,1 s por segundo de video)
        import os
        import queue
        from collections import deque
        from concurrent.futures import ThreadPoolExecutor
        hilos = max(2, min(4, (os.cpu_count() or 4) // 3))
        entradas = queue.Queue(maxsize=12)
        parar = threading.Event()

        def decodificar():
            ultimo = negro
            try:
                for n in range(n_total):
                    if parar.is_set():
                        break
                    t = n / fps_f
                    fondo = None
                    if t < dur:
                        try:
                            fondo = base_de(next(cuadros))
                            ultimo = fondo
                        except StopIteration:
                            fondo = ultimo
                    capas = []
                    for c in clips:
                        if c.ini - 1e-6 <= t < c.fin:
                            a = c.en(t)
                            if a is not None:
                                capas.append(a)
                        elif t >= c.fin and c.c is not None:
                            c.cerrar()
                    entradas.put((n, fondo, capas))
                entradas.put(None)
            except BaseException as e:
                entradas.put(e)

        def mezclar(n, fondo, capas):
            arr = (fondo if fondo is not None else negro).copy()
            for a in capas:
                _mezclar(arr, a)
            nf = av.VideoFrame.from_ndarray(arr, format='rgb24')
            nf.pts = n
            nf.time_base = 1 / fps
            return nf

        hilo_dec = threading.Thread(target=decodificar, daemon=True, name='mp4-neon-decodificar')
        hilo_dec.start()
        cola, fin_entradas = deque(), False
        try:
            with ThreadPoolExecutor(hilos, thread_name_prefix='mp4-neon') as pool:
                while True:
                    while not fin_entradas and len(cola) < 2 * hilos:
                        x = entradas.get()
                        if x is None:
                            fin_entradas = True
                        elif isinstance(x, BaseException):
                            raise x
                        else:
                            cola.append((x[0], pool.submit(mezclar, *x)))
                    if not cola:
                        break
                    n, fut = cola.popleft()
                    nf = fut.result()
                    mirar_cancelar()
                    t = n / fps_f
                    for pk in vs.encode(nf):
                        out.mux(pk)
                    if aus is not None:
                        fin_a = min(mezcla.shape[1], int((t + 0.5) * RSR.SR))
                        while pos_audio + bloque <= fin_a:
                            af = av.AudioFrame.from_ndarray(np.ascontiguousarray(mezcla[:, pos_audio:pos_audio + bloque]), format='fltp', layout='stereo')
                            af.sample_rate = RSR.SR
                            af.pts = pos_audio
                            af.time_base = Fraction(1, RSR.SR)
                            for pk in aus.encode(af):
                                out.mux(pk)
                            pos_audio += bloque
                    if n % 15 == 0:
                        avisar(0.68 + 0.31 * n / max(1, n_total), f'Grabando el Tema 1 en el video… {int(100 * n / max(1, n_total))} %')
        finally:
            parar.set()
            try:
                while True:
                    entradas.get_nowait()
            except queue.Empty:
                pass
            hilo_dec.join(10)
        for pk in vs.encode(None):
            out.mux(pk)
        if aus is not None:
            largo = min(mezcla.shape[1], int(total * RSR.SR))
            while pos_audio < largo:
                trozo = mezcla[:, pos_audio:pos_audio + bloque]
                if trozo.shape[1] < bloque:
                    trozo = np.pad(trozo, ((0, 0), (0, bloque - trozo.shape[1])))
                af = av.AudioFrame.from_ndarray(np.ascontiguousarray(trozo), format='fltp', layout='stereo')
                af.sample_rate = RSR.SR
                af.pts = pos_audio
                af.time_base = Fraction(1, RSR.SR)
                for pk in aus.encode(af):
                    out.mux(pk)
                pos_audio += bloque
            for pk in aus.encode(None):
                out.mux(pk)
        out.close()
        out = None
        entrada.close()
        import os
        os.replace(temporal, destino)
        avisar(1.0, 'Listo')
        return {'ok': True, 'ruta': str(destino), 'segundos': round(time.time() - t_inicio, 1), 'codec': codec, 'cuadros': n_total,
                'con_audio': mezcla is not None, 'pro': con_pro, 'clips': len(clips)}
    except RSR.Cancelado:
        return {'ok': False, 'cancelado': True, 'ruta': None}
    finally:
        for c in clips:
            c.cerrar()
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
