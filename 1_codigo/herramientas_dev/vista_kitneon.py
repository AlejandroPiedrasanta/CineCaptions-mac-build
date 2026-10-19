# CineCaptions · By Cinema Productions
# 1_codigo/herramientas_dev/vista_kitneon.py — v5.5.13: el Tema 1 neón de CUALQUIER video sin Resolve: planifica captions + motions + placa como GO
# (kit_neon, kit_neon_motions, kit_neon_placa), renderiza la placa y fotogramas sueltos de KitNeon encima, y hace una hoja. SOLO desarrollo.
"""
    python 1_codigo/herramientas_dev/vista_kitneon.py <video> <palabras.json> [--idioma es] [--segundos 40] [--cada 2.5] [--usuario @x] [--salida hoja.jpg]
                                                      [--sin-pro]   (solo captions)
"""
import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('video')
    ap.add_argument('palabras')
    ap.add_argument('--idioma', default='es')
    ap.add_argument('--segundos', type=float, default=None)
    ap.add_argument('--cada', type=float, default=2.5)
    ap.add_argument('--usuario', default=None)
    ap.add_argument('--sin-pro', action='store_true')
    ap.add_argument('--salida', default=str(Path(tempfile.gettempdir()) / 'vista_kitneon.jpg'))
    a = ap.parse_args()
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
    dur = float(dur or (w[-1]['end'] + 1.0))
    fps = float(fps or 30)
    t0 = time.time()
    cortes = efectos_visuales.detectar_cortes(video) or []
    cap = KN.escena_captions(w, a.idioma, fin_video=dur)
    mot = [] if a.sin_pro else KM.escena_motions(w, a.idioma, dur, cortes=cortes, video=video, usuario=a.usuario)
    cap = KM.ajustar_captions(cap, mot)
    print(f'plan {time.time() - t0:.1f} s · {len(cap)} captions · motions: ' + ', '.join(f"{m['fn']}@{m['ini']:.1f}" for m in mot))
    hasta = min(dur, a.segundos or dur)
    tmp = Path(tempfile.mkdtemp(prefix='vista_kitneon_'))
    plano = None
    if not a.sin_pro:
        pp = PLA.plan_placa(video, hasta, cap, mot, cortes)
        t0 = time.time()
        plano = PLA.renderizar(video, pp, tmp / 'placa.mp4', fps=fps)
        print(f'placa {time.time() - t0:.1f} s')

    def llam(m):
        return {'fn': m['fn'], 'args': m['a']['_args']} if '_args' in m['a'] else {'fn': m['fn'], 'a': m['a']}
    fondo = [llam(m) for m in mot if m['capa'] == 'fondo']
    medio = [llam(m) for m in mot if m['capa'] == 'delante' and not m.get('cierre') and m['fn'] != 'logoCierre']
    cierre = [llam(m) for m in mot if m.get('cierre')] + [llam(m) for m in mot if m['fn'] == 'logoCierre']
    escena = fondo + medio + cierre + [{'fn': e['fn'], 'a': e['a']} for e in cap] + [llam(m) for m in mot if m['capa'] == 'iconos']
    tiempos = [round(x * a.cada + 1.0, 2) for x in range(int((hasta - 1.0) / a.cada) + 1)]
    props = {'escena': escena, 'imagenes': {}, '_ancho': 1080, '_alto': 1920, '_fps': fps, '_dur': hasta + 0.5, 'tema': 'neon'}
    trab = [{'id': 'KitNeon', 'props': props, 'frame': int(round(t * fps)), 'salida': str(tmp / f'g_{i:03d}.png')} for i, t in enumerate(tiempos)]
    (tmp / 'g.json').write_text(json.dumps({'bundle': str(RM.bundle()), 'navegador': RM._chrome(), 'trabajos': trab}, ensure_ascii=False), encoding='utf-8')
    mjs = RM._render_mjs().with_name('galeria.mjs')
    subprocess.run([RM._node(), str(mjs), str(tmp / 'g.json')], cwd=str(mjs.parent), capture_output=True, timeout=1800)
    fuente = str(plano) if plano else video
    c = av.open(fuente)
    st = c.streams.video[0]
    fotos, k = {}, 0
    for fr in c.decode(st):
        t = float(fr.pts * st.time_base)
        while k < len(tiempos) and t + 1e-3 >= tiempos[k]:
            fotos[k] = fr.to_image().convert('RGBA').resize((1080, 1920))
            k += 1
        if k >= len(tiempos):
            break
    W, H = 270, 480
    cols = 8
    hoja = Image.new('RGB', (W * cols, H * ((len(tiempos) + cols - 1) // cols)), (0, 0, 0))
    for i, t in enumerate(tiempos):
        base = fotos.get(i, Image.new('RGBA', (1080, 1920), (30, 30, 30, 255)))
        g = Path(trab[i]['salida'])
        if g.is_file():
            base.alpha_composite(Image.open(g).convert('RGBA').resize((1080, 1920)))
        im = base.convert('RGB').resize((W, H))
        ImageDraw.Draw(im).text((4, 3), f'{t:.1f}', fill=(255, 255, 0))
        hoja.paste(im, ((i % cols) * W, (i // cols) * H))
    hoja.save(a.salida, quality=86)
    print('hoja:', a.salida)


if __name__ == '__main__':
    main()
