# CineCaptions · By Cinema Productions
# 1_codigo/herramientas_dev/hacer_vistas_crea.py — las 23 previas animadas de «Crea tu estilo» (2_recursos/guia_estilo/crea): GO real en un proyecto temporal y troceado.
r"""
hacer_vistas_crea.py  (v5.75)
-----------------------------
Las previas de la página (cada texto base y cada texto principal SOLO, animado sobre negro) salen de UN render real de Resolve:

  1. entrar  : Resolve abierto y LIBRE (nada del usuario en uso) → proyecto temporal zz_CREA_CC (proyecto_pruebas; el del usuario se guarda)
  2. go      : GO de la app sin pantalla (hacer_vistas_mezcla._go) sobre un video negro con la frase de muestra una vez por look (19 tramos de
               6,5 s), «increíbles» forzada como principal en todos (sin marcas el Tema 4 se queda sin principal y el 6 marca «vean»), solo
               captions. Trampas: LOCALAPPDATA = \\localhost\c$\... (la AppData de Claude guarda motores viejos) y ui.crear_app.
               Después de GO: APAGAR la pista «PRO · Motions completo» si salió y ESPERAR a que la caché de Fusion deje de crecer
               (CacheClip/<uid>, ~2 min) antes de renderizar: un render con la caché llenándose tumbó Resolve.
  3. render  : el timeline a 1080×1920 (MCP cinecaptions «renderizar» → ~/DaVinciSubtitles/banco/<nombre>.mov)
  4. cortar <render> [salida] [ids…] : por los TIEMPOS del plan, la base = lo de antes del bloque de la principal; la principal = desde
               «increíbles», con la base que se queda borrada en 2D (en el Tema 1 se respeta el aro magenta que pasa por encima) y recortada a la
               banda de filas más alta; 16:9, 384×216, 25 fps, entra y se queda 0,9 s.
  5. salir   : cierra y borra zz_CREA_CC y vuelve a cargar el proyecto del usuario; luego borrar ~/DaVinciSubtitles/negro_crea.*, el .mov y
               edicion_pro/<hash> del video negro.

    python hacer_vistas_crea.py entrar | go | cortar <render.mov> [salida] [ids…] | salir
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
CODIGO = AQUI.parent
TRABAJO = Path.home() / 'DaVinciSubtitles' / 'vistas_crea'
LOOKS = ['t1:lima', 't1:magenta', 't1:amarillo', 't2:1', 't2:2', 't2:3', 't2:6', 't2:7', 't2:8', 't3:pila', 't3:select', 't3:shatter', 't3:drag',
         't3:corte', 't3:shine', 't3:resalta', 't4', 't5', 't6']

SEG, T_MAIN = 6.5, 2.40
W, H = 1080, 1100
Y0 = 700                            # (solo la franja central del cuadro de 1080×1920: ahí están todos los captions)
FPS = 30
OW, OH = 384, 216
QUIETO = 0.9
# tramo -> (principal, base, fin de la base relativo al tramo)
CORTES = {0: ('p_t1_circulo', 'b_t1_serif', T_MAIN - 0.05), 1: ('p_t1_subrayado', None, 0), 2: (None, 'b_t1_amano', T_MAIN - 0.05),
          3: ('p_t2_impacto', 'b_t2', 1.62), 4: ('p_t2_editorial', None, 0), 5: ('p_t2_highlight', None, 0), 6: ('p_t2_fire', None, 0),
          7: ('p_t2_strike', None, 0), 8: ('p_t2_underline', None, 0), 9: (None, 'b_t3', T_MAIN - 0.05), 10: ('p_t3_select', None, 0),
          11: ('p_t3_shatter', None, 0), 12: ('p_t3_drag', None, 0), 13: ('p_t3_corte', None, 0), 14: ('p_t3_shine', None, 0),
          15: ('p_t3_resalta', None, 0), 16: ('p_t4', 'b_t4', 2.34), 17: ('p_t5', None, 0), 18: ('p_t6', 'b_t6', 2.34)}


def leer(ruta, t0, t1, gris=False):
    fmt, c = ('gray', 1) if gris else ('rgb24', 3)
    r = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t0:.3f}', '-t', f'{t1 - t0:.3f}', '-i', str(ruta), '-vf', f'crop={W}:{H}:0:{Y0},fps={FPS}', '-f', 'rawvideo',
                        '-pix_fmt', fmt, '-'], capture_output=True)
    a = np.frombuffer(r.stdout, np.uint8)
    return a.reshape(-1, H, W) if gris else a.reshape(-1, H, W, 3)


def dilatar(m, r):
    """Dilatación cuadrada de radio r (sin scipy)."""
    out = m.copy()
    for dy in range(-r, r + 1, max(1, r // 3)):
        for dx in range(-r, r + 1, max(1, r // 3)):
            out |= np.roll(np.roll(m, dy, 0), dx, 1)
    return out


def recorte_temporal(tinta):
    """(i0, i1) sobre la tinta por cuadro: desde que aparece hasta el último cuadro «lleno»."""
    t = tinta.astype(float)
    mx = t.max() or 1.0
    ini = int(np.argmax(t > 0.02 * mx))
    ref = float(np.percentile(t[t > 0.3 * mx], 60)) if (t > 0.3 * mx).any() else mx
    llenos = np.where(t >= 0.88 * ref)[0]
    return max(0, ini - 4), (int(llenos[-1]) + 1) if len(llenos) else len(t)


def rect_16_9(x0, y0, x1, y1, lleno_w=0.84, lleno_h=0.62):
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    cw = max(bw / lleno_w, bh / lleno_h * 16 / 9)
    ch = cw * 9 / 16
    return int(round((x0 + x1) / 2 - cw / 2)), int(round((y0 + y1) / 2 - ch / 2)), int(round(cw)), int(round(ch))


def escribir(destino, cuadros):
    """cuadros: lista de arrays RGB (todos del mismo tamaño 16:9) -> mp4 384×216 a 25 fps con 0,9 s quieto al final."""
    h, w = cuadros[0].shape[:2]
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{w}x{h}', '-r', str(FPS), '-i', '-',
                          '-vf', f'scale={OW}:{OH}:flags=lanczos,fps=25,tpad=stop_mode=clone:stop_duration={QUIETO},format=yuv420p',
                          '-c:v', 'libx264', '-preset', 'slow', '-crf', '20', '-movflags', '+faststart', str(destino)], stdin=subprocess.PIPE)
    for c in cuadros:
        p.stdin.write(np.ascontiguousarray(c).tobytes())
    p.stdin.close()
    p.wait()


def recortar(fr, caja):
    x, y, w, h = rect_16_9(*caja)
    lienzo = np.zeros((len(fr), h, w, 3), np.uint8)
    sx0, sy0, sx1, sy1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    lienzo[:, sy0 - y:sy1 - y, sx0 - x:sx1 - x] = fr[:, sy0:sy1, sx0:sx1]
    return list(lienzo)


def caja_de(tinta2d):
    ys, xs = np.where(tinta2d)
    return (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())) if len(ys) else None


def hacer(render, salida, k, p_id, b_id, fin_base, solo):
    t0 = k * SEG
    if b_id and (not solo or b_id in solo):
        fr = leer(render, t0, t0 + fin_base)
        tinta = fr.max(axis=3) > 60
        i0, i1 = recorte_temporal(fr.max(axis=3).astype(np.float32).sum((1, 2)))      # (por BRILLO: un fundido de salida no cuenta como «lleno»)
        c = caja_de(tinta[i0:i1].any(0))
        if c is None:
            print(f'{b_id}: sin tinta', flush=True)
        else:
            escribir(Path(salida) / f'{b_id}.mp4', recortar(fr[i0:i1], c))
            print(f'{b_id}: {t0 + i0 / FPS:.2f}-{t0 + i1 / FPS:.2f} s, caja {c}', flush=True)
    if p_id and (not solo or p_id in solo):
        fr = leer(render, t0 + T_MAIN - 0.12, t0 + SEG - 0.1).copy()
        if k <= 15:                                                     # Temas 1-3: la base SIGUE en pantalla con la principal: se borra
            antes = leer(render, t0 + T_MAIN - 0.10, t0 + T_MAIN - 0.05)   # (Temas 4-6: la base es otro bloque que ya se fue; borrarla agujereaba)
            base = dilatar(antes.max(axis=3).max(axis=0) > 14, 5)   # (umbral bajo: también el halo de la base)
            for i in range(len(fr)):
                quitar = base
                if k == 0:                                              # el aro magenta del círculo pasa por encima de la base: se queda
                    c_ = fr[i].astype(np.int16)
                    aro = (c_[..., 0] > 110) & (c_[..., 2] > 80) & (c_[..., 1] < c_[..., 0] * 0.6)
                    quitar = base & ~aro
                fr[i][quitar] = 0
        tinta = fr.max(axis=3) > 60
        i0, i1 = recorte_temporal(fr.max(axis=3).astype(np.float32).sum((1, 2)))
        c = caja_de(tinta[i0:i1].any(0))
        if c is None:
            print(f'{p_id}: sin tinta', flush=True)
            return
        # solo el rectángulo de la principal (+8 px): fuera quedaban restos de «se vean»
        tinta_fin = tinta[max(i0, i1 - 10):i1].any(0)
        ys, xs = np.where(tinta_fin)
        if len(ys):
            por_fila = tinta_fin.sum(1)
            llenas = por_fila > max(6, 0.04 * por_fila.max())
            bandas, ini = [], None                                     # la banda de filas MÁS ALTA = la palabra principal (con su aro, caja…)
            for y, v in enumerate(list(llenas) + [False]):
                if v and ini is None:
                    ini = y
                elif not v and ini is not None:
                    if bandas and ini - bandas[-1][1] < 8:
                        bandas[-1] = (bandas[-1][0], y)
                    else:
                        bandas.append((ini, y))
                    ini = None
            y0, y1 = max(bandas, key=lambda b: b[1] - b[0]) if bandas else (int(ys.min()), int(ys.max()))
            m = 8
            fuera = np.ones((H, W), bool)
            fuera[max(0, y0 - m):min(H, y1 + m), max(0, int(xs.min()) - m):min(W, int(xs.max()) + m)] = False
            if k in (10, 12):                                           # (la caja del Select sube y su cursor, como la mano del Drag, baja más)
                fuera[max(0, y0 - int((y1 - y0) * 0.45)):min(H, y1 + int((y1 - y0) * 0.8)), :] = False
            fr[:, fuera] = 0
            tinta = fr.max(axis=3) > 60
            c = caja_de(tinta[i0:i1].any(0)) or c
        escribir(Path(salida) / f'{p_id}.mp4', recortar(fr[i0:i1], c))
        print(f'{p_id}: {t0 + T_MAIN - 0.12 + i0 / FPS:.2f}+{(i1 - i0) / FPS:.2f} s, caja {c}', flush=True)


def entrar():
    sys.path.insert(0, str(CODIGO))
    import proyecto_pruebas as PP
    PP.TEMP = 'zz_CREA_CC'
    print(json.dumps(PP.entrar(), ensure_ascii=False))


def salir():
    sys.path.insert(0, str(CODIGO))
    import proyecto_pruebas as PP
    PP.TEMP = 'zz_CREA_CC'
    print(PP.salir())


def go():
    casa = str(Path.home())                                             # C:\Users\<usuario> -> \\localhost\c$\Users\<usuario>\AppData\Local
    os.environ['LOCALAPPDATA'] = '\\\\localhost\\' + casa[0].lower() + '$' + casa[2:] + '\\AppData\\Local'
    os.environ['CINECAPTIONS_PRO'] = '0'
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    sys.path.insert(0, str(CODIGO))
    os.chdir(CODIGO)
    import qt_kit as ui
    ui.crear_app([], str(CODIGO.parent / '2_recursos' / 'fonts'))         # (sin crear_app los resultados de correr_en_hilo no llegan)
    import hacer_vistas_mezcla as HV
    import mezcla_planificador as MP
    original = MP.planificar

    def con_principal(palabras, looks, *a, **k):
        k['mains'] = [i for i, p in enumerate(palabras) if str(p.get('word') or '').strip(' .,!¡?¿').lower() in ('increíbles', 'increibles')]
        return original(palabras, looks, *a, **k)
    MP.planificar = con_principal
    TRABAJO.mkdir(parents=True, exist_ok=True)
    n = len(LOOKS)
    video = HV.escribir_video_negro(TRABAJO / 'negro_crea.mp4', n * HV.SEGUNDOS + 1.0)
    HV._crear_pack_temporal(TRABAJO / 'packs', LOOKS)
    ok = HV._go(video, HV.palabras_de_muestra(n), TRABAJO / 'packs', tope_s=900, prefs_extra={'go_proyecto': 'actual', 'sfx_emojis': False})
    print('GO ok:', ok, flush=True)
    os._exit(0 if ok else 2)


def cortar_todo(render, salida, solo):
    salida.mkdir(parents=True, exist_ok=True)
    for k, (p_id, b_id, fin_base) in CORTES.items():
        if solo and not ({p_id, b_id} & solo):
            continue
        hacer(render, salida, k, p_id, b_id, fin_base, solo)


if __name__ == '__main__':
    orden = sys.argv[1] if len(sys.argv) > 1 else ''
    if orden == 'cortar':
        render = Path(sys.argv[2])
        salida = Path(sys.argv[3]) if len(sys.argv) > 3 else CODIGO.parent / '2_recursos' / 'guia_estilo' / 'crea'
        cortar_todo(render, salida, set(sys.argv[4:]))
    elif orden in ('entrar', 'go', 'salir'):
        {'entrar': entrar, 'go': go, 'salir': salir}[orden]()
    else:
        print(__doc__)
