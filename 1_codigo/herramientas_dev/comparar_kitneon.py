# CineCaptions · By Cinema Productions
# 1_codigo/herramientas_dev/comparar_kitneon.py — v5.5.13: compara el Tema 1 neón (composición KitNeon de Remotion) con el video de referencia del kit
# «TEMA 1» del usuario, fotograma a fotograma, en una hoja [referencia | CineCaptions]. SOLO desarrollo (no entra en el .exe).
"""
    python 1_codigo/herramientas_dev/comparar_kitneon.py --tiempos 2.0,4.0,7.7 [--kit "<Escritorio>/TEMA 1"] [--escena plan.json] [--salida hoja.jpg]

Sin --escena renderiza el escenas.js del ejemplo (ejemplo_xela) con el MISMO motor portado: sirve para comprobar que el puerto es fiel.
Con --escena (un plan [{fn, a}] hecho por el programa, tiempos de SALIDA) se ve lo que haría CineCaptions con ese video.
El fondo de «CineCaptions» es el fotograma de la FUENTE que corresponde a ese instante (con los cortes del proyecto), sin la cámara ni las pantallas
divididas del kit: compara los gráficos, no la placa.
"""
import argparse
import base64
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
import edicion_pro_remotion as RM  # noqa: E402

KIT = Path.home() / 'Desktop' / 'TEMA 1'


def _datos_L(proyecto):
    txt = (proyecto / 'trabajo' / 'datos.js').read_text(encoding='utf-8')
    return json.loads(txt[txt.index('{'):txt.rindex('}') + 1])


def _imagenes(proyecto, codigo):
    out = {}
    for nombre in sorted(set(re.findall(r"img/[\w\-.]+\.(?:jpg|jpeg|png|webp)", codigo))):
        f = proyecto / nombre
        if f.is_file():
            mime = 'image/png' if f.suffix.lower() == '.png' else 'image/webp' if f.suffix.lower() == '.webp' else 'image/jpeg'
            out[nombre] = f'data:{mime};base64,' + base64.b64encode(f.read_bytes()).decode('ascii')
    return out


def _fuente_de(t, bloques, fps):
    """Instante de SALIDA → fotograma de la FUENTE (los bloques se concatenan 1:1)."""
    f = int(round(t * fps))
    for a, b in bloques:
        if f < b - a:
            return a + f
        f -= b - a
    return bloques[-1][1] - 1


def _salida_de(f_src, bloques):
    """Fotograma de la FUENTE → fotograma de SALIDA (None si cae en un trozo cortado)."""
    acc = 0
    for a, b in bloques:
        if a <= f_src < b:
            return acc + f_src - a
        acc += b - a
    return None


def _fotogramas(video, objetivos):
    """{índice de fotograma: PIL.Image} de un video (solo los pedidos)."""
    import av
    c = av.open(str(video)); st = c.streams.video[0]
    quiero = sorted(set(objetivos)); out = {}; k = 0
    for i, fr in enumerate(c.decode(st)):
        while k < len(quiero) and i >= quiero[k]:
            out[quiero[k]] = fr.to_image().convert('RGB'); k += 1
        if k >= len(quiero):
            break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--kit', default=str(KIT))
    ap.add_argument('--proyecto', default='ejemplo_xela')
    ap.add_argument('--tiempos', required=True)
    ap.add_argument('--escena', default=None)
    ap.add_argument('--referencia', default=None)
    ap.add_argument('--salida', default=str(Path(tempfile.gettempdir()) / 'comparar_kitneon.jpg'))
    ap.add_argument('--ancho', type=int, default=360)
    ap.add_argument('--placa', default=None, help='mp4 de la placa (kit_neon_placa) para el fondo de CineCaptions en vez de la fuente')
    ap.add_argument('--fuente', action='store_true', help='los tiempos son de la FUENTE (captions automáticos sobre el video crudo)')
    a = ap.parse_args()
    kit = Path(a.kit)
    proyecto = kit / a.proyecto
    cfg = json.loads((proyecto / 'proyecto.json').read_text(encoding='utf-8'))
    fps = float(cfg.get('fps') or 30)
    tiempos = [float(x) for x in a.tiempos.split(',') if x.strip()]
    if a.escena:
        props = {'escena': json.loads(Path(a.escena).read_text(encoding='utf-8'))}
        props['imagenes'] = _imagenes(proyecto, json.dumps(props['escena']))
    else:
        codigo = (proyecto / (cfg.get('graficos') or {}).get('escenas', 'escenas.js')).read_text(encoding='utf-8')
        props = {'codigo': codigo, 'L': _datos_L(proyecto), 'imagenes': _imagenes(proyecto, codigo)}
    props.update(_ancho=1080, _alto=1920, _fps=fps, _dur=max(tiempos) + 1.0, tema='neon')
    if a.fuente:                                        # fondo = fuente en ese instante; referencia = su instante de salida
        f_src = [int(round(t * fps)) for t in tiempos]
        f_ref = [_salida_de(f, cfg['bloques']) for f in f_src]
    else:
        f_src = [_fuente_de(t, cfg['bloques'], fps) for t in tiempos]
        f_ref = [int(round(t * fps)) for t in tiempos]
    tmp = Path(tempfile.mkdtemp(prefix='kitneon_'))
    trabajos = [{'id': 'KitNeon', 'props': props, 'frame': int(round(t * fps)), 'salida': str(tmp / f'g_{i:02d}.png')} for i, t in enumerate(tiempos)]
    (tmp / 'galeria.json').write_text(json.dumps({'bundle': str(RM.bundle()), 'navegador': RM._chrome(), 'trabajos': trabajos}, ensure_ascii=False), encoding='utf-8')
    mjs = RM._render_mjs().with_name('galeria.mjs')
    p = subprocess.run([RM._node(), str(mjs), str(tmp / 'galeria.json')], cwd=str(mjs.parent), capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=900)
    for linea in p.stdout.splitlines():
        if '"error"' in linea:
            print(linea)
    from PIL import Image, ImageDraw
    fuente = proyecto / cfg['fuente']
    src = _fotogramas(Path(a.placa) if a.placa else fuente, f_src)
    ref = _fotogramas(Path(a.referencia) if a.referencia else kit / 'entregas' / '3_neon_kinetic_hook.mp4', [f for f in f_ref if f is not None])
    W = a.ancho
    H = int(W * 16 / 9)
    hoja = Image.new('RGB', (W * 2 * min(4, len(tiempos)), H * ((len(tiempos) + 3) // 4)), (0, 0, 0))
    for i, t in enumerate(tiempos):
        r = ref.get(f_ref[i]) if f_ref[i] is not None else None
        base = src.get(f_src[i]).resize((1080, 1920)).convert('RGBA')
        g = Path(trabajos[i]['salida'])
        if g.is_file():
            base.alpha_composite(Image.open(g).convert('RGBA').resize((1080, 1920)))
        x, y = (i % 4) * 2 * W, (i // 4) * H
        if r is not None:
            hoja.paste(r.resize((W, H)), (x, y))
        hoja.paste(base.convert('RGB').resize((W, H)), (x + W, y))
        d = ImageDraw.Draw(hoja)
        d.text((x + 6, y + 4), f'REF {t:.2f}', fill=(255, 255, 0))
        d.text((x + W + 6, y + 4), f'CC {t:.2f}', fill=(0, 255, 255))
    hoja.save(a.salida, quality=86)
    print('hoja:', a.salida)


if __name__ == '__main__':
    main()
