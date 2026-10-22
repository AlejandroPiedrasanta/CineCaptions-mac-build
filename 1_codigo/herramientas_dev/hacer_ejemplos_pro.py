# CineCaptions · By Cinema Productions
# 1_codigo/herramientas_dev/hacer_ejemplos_pro.py — los EJEMPLOS REALES de los interruptores de la Edición PRO en Proyecto (pro_lateral_ui): un clip
# de 4 s por interruptor (a la proporción de la PANTALLA del móvil de Proyecto, ~9:19,5: la llena sin franjas) = un video real de una persona + el motion de Remotion que pone la PRO (con alfa) y, donde va DETRÁS de la persona,
# su recorte con la IA local (edicion_pro_persona). Salen en 2_recursos/edicion_pro/ejemplos_pro/<clave>.mp4 (+ <clave>.jpg, el póster).
#     python 1_codigo/herramientas_dev/hacer_ejemplos_pro.py [<video persona vertical>] [--guion <x.guion.json>] [--solo pildora,broll] [--rehacer]
# Por defecto: «Desktop/VIDEOS EN ESPAÑOL/PRUEBA ESPAÑOL.mp4» y su guion.json de ~/DaVinciSubtitles (los captions dicen lo que se dice de verdad).
import argparse
import base64
import io
import json
import math
import sys
import tempfile
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent.parent
sys.path.insert(0, str(AQUI.parent))
import edicion_pro_remotion as RM  # noqa: E402
import edicion_pro_persona as PE  # noqa: E402
import pro_lateral_ui as PL  # noqa: E402



def _alto_pantalla(ancho):
    """El alto (par) para ese ancho con la proporción de la pantalla del marco del móvil (2_recursos/creativo/movil.json, el de Creativo)."""
    try:
        i = json.loads((RAIZ / '2_recursos' / 'creativo' / 'movil.json').read_text(encoding='utf-8'))
        a = i['pantalla']
        asp = (a[2] - a[0]) * float(i['aspecto']) / (a[3] - a[1])
    except Exception:
        asp = 0.4612
    return int(round(ancho / asp / 2.0)) * 2


W, FPS, DUR = 432, 30, 4.0
H = _alto_pantalla(W)
N = int(DUR * FPS)
VIDEO = Path.home() / 'Desktop' / 'VIDEOS EN ESPAÑOL' / 'PRUEBA ESPAÑOL.mp4'
GUION = Path.home() / 'DaVinciSubtitles' / 'CineCaptions _ PRUEBA ESPAÑOL_audio.es.guion.json'
LETRA_CAP = RAIZ / '2_recursos' / 'fonts' / 'Inter_24pt-Bold.ttf'
LETRA_TIT = RAIZ / '2_recursos' / 'edicion_pro' / 'fuentes_extra' / 'Anton-Regular.ttf'
ICONOS = ['3d:crown-dynamic-color', '3d:bell-dynamic-color', '3d:camera-dynamic-premium', '3d:calendar-dynamic-color']

# el tramo del video (s) de cada ejemplo, elegido por lo que se dice en PRUEBA ESPAÑOL (un video real de un festival en Xela)
# (con la persona en cámara: 10–13, 16–21, 43–46, 52–62 s; 47–51 es el cartel del festival y 32–41 el concierto)
TRAMOS = {'gancho': 0.0, 'detras': 15.6, 'pildora': 51.9, 'broll': 19.6, 'motions_completo': 28.6, 'escenas': 56.0, 'kit': 43.6,
          'graficos': 5.4, 'plantillas': 53.8, 'emoji': 51.9}
# cuándo entra el motion dentro del ejemplo (s): cuando se dice la palabra que lo pide
ENTRA = {'pildora': 0.3, 'broll': 1.2, 'escenas': 0.5, 'kit': 1.1, 'graficos': 1.8, 'plantillas': 0.7, 'emoji': 0.3}


# ----------------------------------------------------------------------------------------------------------------------- video y voz
def cuadros(video, t0):
    """N cuadros RGB uint8 (H, W, 3) desde t0, a FPS: el video CUBRE el cuadro (se recorta lo que sobra a los lados, centrado)."""
    import av
    out = []
    with av.open(str(video)) as c:
        st = c.streams.video[0]
        sw, sh = st.codec_context.width, st.codec_context.height
        esc = max(W / sw, H / sh)
        rw, rh = max(W, int(round(sw * esc / 2.0)) * 2), max(H, int(round(sh * esc / 2.0)) * 2)
        x0, y0 = (rw - W) // 2, (rh - H) // 2
        c.seek(int(max(0.0, t0 - 1.0) / st.time_base), stream=st)
        for f in c.decode(st):
            if f.time is None or f.time < t0 - 0.5 / FPS:
                continue
            out.append(np.ascontiguousarray(f.to_ndarray(format='rgb24', width=rw, height=rh)[y0:y0 + H, x0:x0 + W]))
            if len(out) >= N:
                break
    while len(out) < N:
        out.append(out[-1])
    return out


def palabras(guion, t0):
    """[(texto, t relativo)] de las palabras dichas en [t0, t0 + DUR)."""
    d = json.loads(Path(guion).read_text(encoding='utf-8'))
    out = []
    for cue in d.get('cues') or []:
        for r in cue.get('runs') or []:
            t = float(r.get('t') or cue.get('start') or 0) - t0
            if -0.05 <= t < DUR:
                out.append((str(r.get('texto') or '').strip(), max(0.0, t)))
    return out


def mates(frames):
    """La silueta (H, W) float 0..1 de la persona en cada cuadro (IA local)."""
    return [PE.refinar_alfa(PE.mate(f), W, H).astype(np.float32) / 255.0 for f in frames]


def cabeza(mate):
    """(x, y) en % del centro de la cabeza (la fila más alta de la silueta + un poco)."""
    filas = np.where(mate.max(axis=1) > 0.5)[0]
    if not len(filas):
        return 50.0, 30.0
    top = int(filas[0])
    banda = mate[top:top + int(0.08 * H)]
    xs = np.where(banda.max(axis=0) > 0.5)[0]
    x = float(xs.mean()) if len(xs) else W / 2
    return round(100 * x / W, 1), round(100 * (top + 0.075 * H) / H, 1)


# ----------------------------------------------------------------------------------------------------------------------- capas
def remotion(lista, carpeta):
    """[(clave, comp, props, dur)] → {clave: [cuadros RGBA float]} (render con alfa; cada cuadro, a su tiempo dentro del ejemplo)."""
    import av
    trabajos = []
    for clave, comp, props, dur in lista:
        p = dict(props, _ancho=W, _alto=H, _fps=FPS, _dur=float(dur))
        trabajos.append({'id': comp, 'props': p, 'salida': RM.salida_para(comp, p, carpeta), 'clave': clave})
    res = RM.renderizar([{k: v for k, v in t.items() if k != 'clave'} for t in trabajos], timeout=1200)
    out = {}
    for t in trabajos:
        if not res.get(str(t['salida'])):
            print('  FALLO el render de', t['clave'], t['id'])
            continue
        fr = []
        with av.open(str(t['salida'])) as c:
            for f in c.decode(video=0):
                fr.append(f.to_ndarray(format='rgba').astype(np.float32) / 255.0)
        out[t['clave']] = fr
    return out


def sobre(base, capa):
    """base RGB float (H, W, 3) 0..1 con una capa RGBA float encima."""
    a = capa[..., 3:4]
    return base * (1.0 - a) + capa[..., :3] * a


def capa_en(fr, i, desde=0.0):
    """El cuadro de una capa de Remotion que toca en el cuadro i del ejemplo (empieza en `desde` s); None fuera de su tiempo."""
    k = i - int(round(desde * FPS))
    return fr[k] if fr and 0 <= k < len(fr) else None


def _fuente(ruta, tam):
    from PIL import ImageFont
    return ImageFont.truetype(str(ruta), int(tam))


def texto_rgba(lineas, letra, tam, y, color=(255, 255, 255), sombra=True, escala=1.0, alfa=1.0):
    """Una capa RGBA float (H, W, 4) con líneas centradas (y = centro de la primera línea, fracción del alto) y una sombra suave debajo."""
    from PIL import Image, ImageDraw, ImageFilter
    out = np.zeros((H, W, 4), np.float32)
    if not lineas or alfa <= 0.01:
        return out
    img = Image.new('L', (W, H), 0)
    f = _fuente(letra, tam * escala)
    d = ImageDraw.Draw(img)
    ancho = max(d.textlength(ln, font=f) for ln in lineas)
    if ancho > 0.9 * W:                                  # que quepa: se achica la letra
        escala *= 0.9 * W / ancho
        f = _fuente(letra, tam * escala)
    for k, ln in enumerate(lineas):
        d.text((W / 2, y * H + k * tam * escala * 1.05), ln, font=f, fill=255, anchor='mm')
    ta = np.asarray(img).astype(np.float32) / 255.0
    out[..., :3] = np.array(color, np.float32) / 255.0
    if sombra:
        sa = np.asarray(img.filter(ImageFilter.GaussianBlur(max(2.0, tam * escala / 14.0)))).astype(np.float32) / 255.0 * 0.65
        sa = np.roll(sa, 3, axis=0)
        a = ta + sa * (1.0 - ta)
        out[..., :3] *= (ta / np.maximum(a, 1e-4))[..., None]
        out[..., 3] = a
    else:
        out[..., 3] = ta
    out[..., 3] *= alfa
    return out


def _pop(q):
    """0 → 1 con un pequeño rebote (la entrada de una palabra)."""
    q = max(0.0, min(1.0, q))
    return 1.0 - math.exp(-7.0 * q) * math.cos(10.0 * q)


def captions(pal, t, y=0.58, max_pal=4):
    """Los captions palabra a palabra del instante t (como los de GO): las últimas palabras dichas, la nueva entra con un pop."""
    dichas = [(w, a) for w, a in pal if a <= t]
    if not dichas:
        return None
    grupo = dichas[-max_pal:]
    if len(dichas) > max_pal:                           # cada bloque se limpia al llenarse
        grupo = dichas[(len(dichas) - 1) // max_pal * max_pal:]
    lineas = _partir(' '.join(w for w, _a in grupo).upper(), 18)
    while len(lineas) > 2 and len(grupo) > 1:            # como GO: nunca más de 2 líneas (la 3.ª tapaba la píldora de debajo)
        grupo = grupo[1:]
        lineas = _partir(' '.join(w for w, _a in grupo).upper(), 18)
    q = (t - grupo[-1][1]) / 0.18
    return texto_rgba(lineas[-2:], LETRA_CAP, 34, y, escala=0.92 + 0.08 * _pop(q), alfa=min(1.0, 0.4 + q))


def _partir(texto, n):
    out, ln = [], ''
    for w in texto.split():
        if ln and len(ln) + 1 + len(w) > n:
            out.append(ln)
            ln = w
        else:
            ln = (ln + ' ' + w).strip()
    return out + ([ln] if ln else [])


def foto_data(ruta):
    from PIL import Image
    im = Image.open(ruta).convert('RGB')
    im.thumbnail((720, 1280))
    b = io.BytesIO()
    im.save(b, 'JPEG', quality=86)
    return 'data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode('ascii')


# ----------------------------------------------------------------------------------------------------------------------- los ejemplos
def hacer(clave, video, guion, carpeta):
    t0 = TRAMOS[clave]
    fr = cuadros(video, t0)
    pal = palabras(guion, t0)
    base = [f.astype(np.float32) / 255.0 for f in fr]
    out = []
    if clave == 'motions_completo':                     # el de verdad: motions_completo.crear sobre este tramo
        import av
        import motions_completo as MCO
        tramo = Path(carpeta) / 'tramo_mc.mp4'
        with av.open(str(tramo), 'w') as o:
            s = o.add_stream('libx264', rate=FPS)
            s.width, s.height, s.pix_fmt = W, H, 'yuv420p'
            for f in fr:
                for p in s.encode(av.VideoFrame.from_ndarray(f, format='rgb24')):
                    o.mux(p)
            for p in s.encode():
                o.mux(p)
        bl, cur = [], None
        for w, a in pal:
            if cur is None or a - cur['ini'] > 1.6:
                cur = {'ini': a, 'fin': a + 0.4, 'palabras': []}
                bl.append(cur)
            cur['palabras'].append({'texto': w, 't': round(a - cur['ini'], 3)})
            cur['fin'] = a + 0.45
        mc = MCO.crear(bl, DUR, W, H, FPS, carpeta, 'es', {}, str(tramo), lambda t: None, ia=False)
        if not mc:
            raise SystemExit('Motions completo no salió')
        return [f / 255.0 for f in cuadros(mc, 0.0)]
    detras = clave in ('gancho', 'detras')
    alfa = mates(fr) if detras else None
    capas = {}
    if clave == 'gancho':
        cx, cy = cabeza(alfa[int(FPS)])
        orb = {'iconos': ICONOS, 'x': cx, 'y': cy, 'rx': 30, 'ry': 6, 'escala': 1.3, 'vuelta': 2.8, 'inclinacion': -6}
        capas = remotion([('atras', 'OrbitaT5', dict(orb, lado='atras'), 3.4), ('delante', 'OrbitaT5', dict(orb, lado='delante'), 3.4)], carpeta)
    elif clave == 'pildora':
        capas = remotion([('p', 'AcompananteT5', {'tipo': 'cifra', 'valor': '100', 'signo': '%', 'texto': 'Gratuita', 'y': 74, 'aspecto': 'cristal',
                                                   'escala': 1.3}, 3.6)],
                         carpeta)
    elif clave == 'broll':
        capas = remotion([('p', 'FotoE', {'foto': foto_data(RAIZ / '2_recursos' / 'fondos_estilos' / 'fondo_03.jpg'), 'palabra': 'EUROPA'}, 2.9)], carpeta)
    elif clave == 'escenas':
        capas = remotion([('p', 'ChatE', {'mensaje': '¿Vamos al festival?', 'respuesta': '¡Nos vemos ahí!', 'etiqueta': 'Tus amigos'}, 3.5)], carpeta)
    elif clave == 'kit':
        capas = remotion([('p', 'CalendarioK', {'desde': 1, 'hasta': 10, 'etiqueta': 'OCTUBRE', 'y': 36}, 2.9)], carpeta)
    elif clave == 'graficos':
        capas = remotion([('p', 'Ubicacion', {'pais': 'gt', 'nombre': 'Quetzaltenango', 'kicker': 'UBICACIÓN'}, 2.2)], carpeta)
    elif clave == 'plantillas':
        capas = remotion([('p', 'Pastilla', {'texto': 'GUÁRDALO PARA DESPUÉS', 'estilo': 'blanco', 'sticker': 'emoji:pushpin', 'y': 30, 'escala': 1.8}, 3.3)], carpeta)
    elif clave == 'emoji':                              # v5.25: el MISMO EmojiPro que pone GO (🎉 de Lottie, con rebote) junto a los captions
        capas = remotion([('p', 'EmojiPro', {'id': 'party_popper', 'variante': 'rebote', 'fuente': 'lottie', 'lottie': None, 'imagen': None,
                                             'x': 74, 'y': 50, 'tamano': 24, 'energia': 1.0, 'acento': '#FFC24D'}, 3.6)], carpeta)
    empieza = ENTRA.get(clave, 0.0)
    for i in range(N):
        t = i / FPS
        img = base[i]
        if clave == 'gancho':
            q = t / 0.35
            tit = texto_rgba(['¿VIVES O', 'ESTÁS DE PASO?'], LETRA_TIT, 92, 0.36, color=(255, 214, 92), escala=0.85 + 0.15 * _pop(q),
                             alfa=min(1.0, q) * (1.0 if t < 3.2 else max(0.0, 1.0 - (t - 3.2) / 0.4)))
            img = sobre(img, tit)
            c = capa_en(capas.get('atras'), i)
            if c is not None:
                img = sobre(img, c)
            a = alfa[i][..., None]
            img = img * (1.0 - a) + base[i] * a                # la persona, delante
            c = capa_en(capas.get('delante'), i)
            if c is not None:
                img = sobre(img, c)
        elif clave == 'detras':
            dichas = [(w, a) for w, a in pal if a <= t]
            if dichas:
                grupo = dichas[(len(dichas) - 1) // 2 * 2:]             # de dos en dos, como los captions grandes de la PRO
                q = (t - grupo[-1][1]) / 0.2
                cap = texto_rgba(_partir(' '.join(w for w, _a in grupo).upper(), 9), LETRA_TIT, 118, 0.27, escala=0.9 + 0.1 * _pop(q),
                                 alfa=min(1.0, 0.3 + q))
                img = sobre(img, cap)
            a = alfa[i][..., None]
            img = img * (1.0 - a) + base[i] * a
        else:
            if clave not in ('escenas', 'graficos') or capa_en(next(iter(capas.values()), None), i, empieza) is None:
                cap = captions(pal, t, y=0.62 if clave == 'pildora' else 0.66)
                if cap is not None:
                    img = sobre(img, cap)
            c = capa_en(next(iter(capas.values()), None), i, empieza)
            if c is not None:
                img = sobre(img, c)
        out.append(np.clip(img, 0.0, 1.0))
    return out


def guardar(frames, mp4, jpg):
    import av
    from PIL import Image
    mp4.parent.mkdir(parents=True, exist_ok=True)
    with av.open(str(mp4), 'w', options={'movflags': 'faststart'}) as o:
        s = o.add_stream('libx264', rate=FPS)
        s.width, s.height, s.pix_fmt = W, H, 'yuv420p'
        s.options = {'crf': '25', 'preset': 'slow'}
        for f in frames:
            for p in s.encode(av.VideoFrame.from_ndarray((f * 255).astype(np.uint8), format='rgb24')):
                o.mux(p)
        for p in s.encode():
            o.mux(p)
    Image.fromarray((frames[int(len(frames) * 0.62)] * 255).astype(np.uint8)).save(jpg, quality=86, optimize=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('video', nargs='?', default=str(VIDEO))
    ap.add_argument('--guion', default=str(GUION))
    ap.add_argument('--solo', default='')
    ap.add_argument('--rehacer', action='store_true')
    a = ap.parse_args()
    solo = [s for s in a.solo.split(',') if s]
    destino = PL.carpeta_ejemplos()
    carpeta = Path(tempfile.mkdtemp(prefix='ejemplos_pro_'))
    for op in PL.OPCIONES:
        clave = op['clave']
        if (solo and clave not in solo) or clave not in TRAMOS:
            continue
        mp4 = destino / (clave + '.mp4')
        if mp4.exists() and not a.rehacer:
            continue
        print('·', clave, '…', flush=True)
        guardar(hacer(clave, a.video, a.guion, carpeta), mp4, mp4.with_suffix('.jpg'))
        print('  ->', mp4, round(mp4.stat().st_size / 1024), 'KB', flush=True)


if __name__ == '__main__':
    main()
