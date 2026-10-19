# CineCaptions · By Cinema Productions
# 1_codigo/herramientas_dev/comparar_ref_neon.py — v5.5.13: el Tema 1 neón contra REFERENCIA.mp4 (entregas/3_neon_kinetic_hook.mp4) fotograma a
# fotograma, ALINEADO por la EDL del kit (proyecto.json «bloques»: la referencia quita 3 frases y añade 1,2 s de cierre). SOLO desarrollo.
"""
    python 1_codigo/herramientas_dev/comparar_ref_neon.py render <nuestro.mp4> <prefijo> [--paso 1] [--desde 0] [--hasta 53.1]   (un render de Resolve)
    python 1_codigo/herramientas_dev/comparar_ref_neon.py vista <video> <palabras.json> <prefijo> [--placa placa.mp4] [...]       (sin Resolve: placa + KitNeon)
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

CODIGO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CODIGO))

import av
from PIL import Image, ImageDraw

KIT = Path.home() / 'Desktop' / 'TEMA 1' / 'ejemplo_xela'
REF = Path.home() / 'Desktop' / 'REFERENCIA.mp4'


def edl():
    pj = json.loads((KIT / 'proyecto.json').read_text(encoding='utf-8'))
    return [tuple(b) for b in pj['bloques']], float(pj.get('fps') or 30)


def fuente_de(t, bloques, fps):
    """Segundo de la fuente que se ve en el segundo `t` de la referencia (None = cierre gráfico)."""
    acc = 0.0
    for a, b in bloques:
        d = (b - a) / fps
        if t < acc + d:
            return a / fps + (t - acc)
        acc += d
    return None


def fotos(video, tiempos, ancho):
    c = av.open(str(video))
    st = c.streams.video[0]
    out, pend = {}, sorted(set(tiempos))
    k = 0
    for fr in c.decode(st):
        tt = float(fr.pts * st.time_base)
        while k < len(pend) and tt + 1e-3 >= pend[k]:
            im = fr.to_image().convert('RGB')
            out[pend[k]] = im.resize((ancho, int(round(ancho * im.height / im.width))))
            k += 1
        if k >= len(pend):
            break
    c.close()
    return out


def main_render(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('nuestro')
    ap.add_argument('salida')
    ap.add_argument('--paso', type=float, default=1.0)
    ap.add_argument('--desde', type=float, default=0.0)
    ap.add_argument('--hasta', type=float, default=53.1)
    ap.add_argument('--ancho', type=int, default=300)
    ap.add_argument('--por_hoja', type=int, default=12)
    ap.add_argument('--fin-video', type=float, default=None, help='s que dura el video en NUESTRO render: el cierre de la referencia se compara con lo de después')
    a = ap.parse_args(argv)
    bloques, fps = edl()
    fin_ref = sum((b - x) / fps for x, b in bloques)
    ts = [round(a.desde + k * a.paso, 3) for k in range(int((a.hasta - a.desde) / a.paso) + 1)]
    src = {t: fuente_de(t, bloques, fps) if t < fin_ref or a.fin_video is None else a.fin_video + (t - fin_ref) for t in ts}
    r = fotos(REF, ts, a.ancho)
    n = fotos(a.nuestro, [s for s in src.values() if s is not None], a.ancho)
    h = int(round(a.ancho * 1920 / 1080))
    hojas = []
    for i in range(0, len(ts), a.por_hoja):
        grupo = ts[i:i + a.por_hoja]
        cols = 6
        filas = (len(grupo) + cols - 1) // cols
        hoja = Image.new('RGB', (cols * (2 * a.ancho + 12), filas * (h + 4)), (0, 0, 0))
        d = ImageDraw.Draw(hoja)
        for j, t in enumerate(grupo):
            x, y = (j % cols) * (2 * a.ancho + 12), (j // cols) * (h + 4)
            if t in r:
                hoja.paste(r[t], (x, y))
            s = src[t]
            if s is not None and s in n:
                hoja.paste(n[s], (x + a.ancho + 2, y))
            d.rectangle([x, y, x + 150, y + 18], fill=(0, 0, 0))
            d.text((x + 3, y + 3), f'REF {t:.1f}  NUESTRO {s:.1f}' if s is not None else f'REF {t:.1f} (cierre)', fill=(255, 255, 0))
        ruta = f'{a.salida}_{i // a.por_hoja + 1}.jpg'
        hoja.save(ruta, quality=88)
        hojas.append(ruta)
    print('\n'.join(hojas))



def main_vista(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('video')
    ap.add_argument('palabras')
    ap.add_argument('salida')
    ap.add_argument('--paso', type=float, default=1.0)
    ap.add_argument('--desde', type=float, default=0.0)
    ap.add_argument('--hasta', type=float, default=53.0)
    ap.add_argument('--ancho', type=int, default=220)
    ap.add_argument('--placa', default='')
    a = ap.parse_args(argv)
    import av
    import edicion_pro as EP
    import edicion_pro_remotion as RM
    import efectos_visuales
    import kit_neon as KN
    import kit_neon_motions as KM
    import kit_neon_placa as PLA
    from PIL import Image, ImageDraw
    video = str(Path(a.video).resolve())
    w = json.loads(Path(a.palabras).read_text(encoding='utf-8'))
    w = w.get('palabras') if isinstance(w, dict) else w
    _w, _h, dur, fps = EP.medir(video)
    dur, fps = float(dur), float(fps or 30)
    cortes = efectos_visuales.detectar_cortes(video) or []
    cap = KN.escena_captions(w, 'es', fin_video=dur)
    mot = KM.escena_motions(w, 'es', dur, cortes=cortes, video=video)
    cap = KM.ajustar_captions(cap, mot)
    print('motions:', ', '.join(f"{m['fn']}@{m['ini']:.1f}" for m in mot), flush=True)
    tmp = Path(tempfile.mkdtemp(prefix='cmp_vista_'))
    placa = Path(a.placa) if a.placa else tmp / 'placa.mp4'
    if not placa.exists():
        t0 = time.time()
        PLA.renderizar(video, PLA.plan_placa(video, dur, cap, mot, cortes), placa, fps=fps)
        print(f'placa {time.time() - t0:.0f} s: {placa}', flush=True)
    bloques, fps_k = edl()
    fin_ref = sum((b - x) / fps_k for x, b in bloques)
    ts = [round(a.desde + k * a.paso, 3) for k in range(int((a.hasta - a.desde) / a.paso) + 1)]
    src = {t: (fuente_de(t, bloques, fps_k) if t < fin_ref else dur + (t - fin_ref)) for t in ts}

    def llam(m):
        return {'fn': m['fn'], 'args': m['a']['_args']} if '_args' in m['a'] else {'fn': m['fn'], 'a': m['a']}
    fondo = [llam(m) for m in mot if m['capa'] == 'fondo']
    medio = [llam(m) for m in mot if m['capa'] == 'delante' and not m.get('cierre') and m['fn'] != 'logoCierre']
    cierre = [llam(m) for m in mot if m.get('cierre')] + [llam(m) for m in mot if m['fn'] == 'logoCierre']
    escena = fondo + medio + cierre + [{'fn': e['fn'], 'a': e['a']} for e in cap] + [llam(m) for m in mot if m['capa'] == 'iconos']
    props = {'escena': escena, 'imagenes': {}, '_ancho': 1080, '_alto': 1920, '_fps': fps, '_dur': dur + 2.0, 'tema': 'neon'}
    trab = [{'id': 'KitNeon', 'props': props, 'frame': int(round(s * fps)), 'salida': str(tmp / f'g_{i:03d}.png')} for i, s in enumerate(src[t] for t in ts)]
    (tmp / 'g.json').write_text(json.dumps({'bundle': str(RM.bundle()), 'navegador': RM._chrome(), 'trabajos': trab}, ensure_ascii=False), encoding='utf-8')
    mjs = RM._render_mjs().with_name('galeria.mjs')
    t0 = time.time()
    subprocess.run([RM._node(), str(mjs), str(tmp / 'g.json')], cwd=str(mjs.parent), capture_output=True, timeout=3600)
    print(f'gráficos {time.time() - t0:.0f} s', flush=True)
    base = fotos(placa, [s for s in src.values() if s < dur - 0.02], 1080)
    nuestros = {}
    for i, t in enumerate(ts):
        s = src[t]
        im = base.get(s, Image.new('RGB', (1080, 1920), (0, 0, 0))).convert('RGBA').resize((1080, 1920))
        g = Path(trab[i]['salida'])
        if g.is_file():
            im.alpha_composite(Image.open(g).convert('RGBA').resize((1080, 1920)))
        nuestros[t] = im.convert('RGB').resize((a.ancho, int(round(a.ancho * 1920 / 1080))))
    ref = fotos(REF, ts, a.ancho)
    h = int(round(a.ancho * 1920 / 1080))
    for j0 in range(0, len(ts), 12):
        grupo = ts[j0:j0 + 12]
        cols = 6
        hoja = Image.new('RGB', (cols * (2 * a.ancho + 12), ((len(grupo) + cols - 1) // cols) * (h + 4)), (0, 0, 0))
        d = ImageDraw.Draw(hoja)
        for j, t in enumerate(grupo):
            x, y = (j % cols) * (2 * a.ancho + 12), (j // cols) * (h + 4)
            if t in ref:
                hoja.paste(ref[t], (x, y))
            hoja.paste(nuestros[t], (x + a.ancho + 2, y))
            d.rectangle([x, y, x + 150, y + 18], fill=(0, 0, 0))
            d.text((x + 3, y + 3), f'REF {t:.1f}  NUESTRO {src[t]:.1f}', fill=(255, 255, 0))
        ruta = f'{a.salida}_{j0 // 12 + 1}.jpg'
        hoja.save(ruta, quality=88)
        print(ruta, flush=True)



if __name__ == '__main__':
    modo = sys.argv[1] if len(sys.argv) > 1 else ''
    if modo == 'render':
        main_render(sys.argv[2:])
    elif modo == 'vista':
        main_vista(sys.argv[2:])
    else:
        print(__doc__)
