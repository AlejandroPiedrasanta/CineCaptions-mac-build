# CineCaptions · By Cinema Productions
# 1_codigo/herramientas_dev/galeria_remotion.py — la galería de las 100 plantillas Remotion de la Edición PRO: un fotograma de cada una sobre un
# fotograma de video, en hojas por rama (para revisarlas y enseñarlas).
#     python 1_codigo/herramientas_dev/galeria_remotion.py [--video <mp4 de fondo>] [--salida <carpeta>] [--rama bodas]
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
import edicion_pro_catalogo as C  # noqa: E402
import edicion_pro_remotion as RM  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--video', default='')
    ap.add_argument('--salida', default=str(Path.home() / 'DaVinciSubtitles' / 'edicion_pro' / 'galeria'))
    ap.add_argument('--rama', default='')
    a = ap.parse_args()
    out = Path(a.salida)
    out.mkdir(parents=True, exist_ok=True)
    plantillas = [p for p in C.PLANTILLAS if not a.rama or p['rama'] == a.rama]
    trabajos = []
    for p in plantillas:
        props = dict(p['props'], _ancho=540, _alto=960, _fps=30, _dur=p['dur'])
        trabajos.append({'id': p['comp'], 'props': props, 'frame': int(p['dur'] * 30 * 0.62), 'salida': str(out / f"{p['id']}.png")})
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump({'bundle': str(RM.bundle()), 'navegador': RM._chrome(), 'trabajos': trabajos}, f, ensure_ascii=False)
    mjs = AQUI.parent / 'remotion' / 'galeria.mjs'
    subprocess.run([RM._node(), str(mjs), f.name], cwd=str(mjs.parent), check=False)
    # hojas por rama, sobre un fotograma de video (o un degradado)
    from PIL import Image, ImageDraw
    fondo = None
    if a.video:
        try:
            import av
            with av.open(a.video) as c:
                for fr in c.decode(c.streams.video[0]):
                    fondo = fr.to_image().convert('RGB')
                    break
        except Exception:
            fondo = None
    for rama in sorted({p['rama'] for p in plantillas}):
        items = [p for p in plantillas if p['rama'] == rama]
        col, w, h = 8, 270, 480
        hoja = Image.new('RGB', (col * (w + 6), ((len(items) + col - 1) // col) * (h + 30)), (24, 24, 28))
        d = ImageDraw.Draw(hoja)
        for k, p in enumerate(items):
            base = (fondo.resize((w, h)) if fondo else Image.new('RGB', (w, h), (70, 80, 95))).convert('RGBA')
            f2 = out / f"{p['id']}.png"
            if f2.exists():
                im = Image.open(f2).convert('RGBA').resize((w, h))
                base.alpha_composite(im)
            x, y = (k % col) * (w + 6), (k // col) * (h + 30)
            hoja.paste(base.convert('RGB'), (x, y))
            d.text((x + 4, y + h + 6), p['id'], fill=(230, 230, 230))
        hoja.save(out / f'galeria_{rama}.png')
        print('hoja', rama, len(items))


if __name__ == '__main__':
    main()
