# CineCaptions · By Cinema Productions
# 1_codigo/herramientas_dev/hacer_previas_motions.py — las miniaturas del carrusel «Motions de la Edición PRO» (página Efectos): un fotograma de cada
# motion del catálogo (motions_catalogo.catalogo()) que sea una composición de Remotion, sobre un fondo neutro, en
# 2_recursos/edicion_pro/previas_motions/<id con «:» → «_»>.jpg. Los que no son de Remotion (gráficos OGraf, Tema 5) se dibujan en la tarjeta.
#     python 1_codigo/herramientas_dev/hacer_previas_motions.py [--solo kit,escena] [--rehacer]
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
import edicion_pro_remotion as RM  # noqa: E402
import motions_catalogo as MC  # noqa: E402

# props de muestra para las composiciones del kit y de las escenas (las plantillas traen las suyas en el catálogo)
_MUESTRA = {'titulo': 'Tres razones', 'kicker': 'TIP', 'subtitulo': 'para empezar hoy', 'texto': 'Empieza hoy',
            'items': ['Constancia', 'Enfoque', 'Paciencia'], 'lista': ['Constancia', 'Enfoque', 'Paciencia'],
            'palabras': ['Constancia', 'Enfoque', 'Paciencia'], 'cifra': '87%', 'numero': 87, 'valor': '87%', 'unidad': '%'}
_ICONOS = ['3d:crown-dynamic-color', '3d:bell-dynamic-color', '3d:camera-dynamic-premium', '3d:calendar-dynamic-color']
_PROPIAS = {'acompanante': {'tipo': 'sticker', 'texto': 'Boda', 'sticker': 'emoji:rose'},
            't5:orbita': {'iconos': _ICONOS, 'y': 34, 'rx': 36, 'ry': 7, 'escala': 1.5},
            't5:escena': {'variante': 'icono', 'etiqueta': 'Tres razones', 'icono': 'crown-dynamic-color', 'fondo': 'papel', 'y': 50},
            't5:pasos': {'n': 4, 'actual': 1, 'y': 50}, 't5:deslizador': {'y': 50}}
_SIN_PREVIA = {'escena:foto', 't5:sticker'}             # necesitan una foto o un fotograma del video: la tarjeta se dibuja sola


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--solo', default='')
    ap.add_argument('--rehacer', action='store_true')
    a = ap.parse_args()
    solo = {s for s in a.solo.split(',') if s}
    destino = MC.carpeta_previas()
    destino.mkdir(parents=True, exist_ok=True)
    crudos = Path(tempfile.mkdtemp(prefix='previas_motions_'))
    trabajos, por_id = [], {}
    for m in MC.catalogo():
        if not m.get('comp') or m['id'] in _SIN_PREVIA or (solo and m['grupo'] not in solo):
            continue
        final = destino / MC.archivo_previa(m['id'])
        if final.exists() and not a.rehacer:
            continue
        props = dict(m.get('props') or _PROPIAS.get(m['id']) or _MUESTRA)
        props.update(_ancho=540, _alto=960, _fps=30, _dur=float(m.get('dur') or 3.0))
        png = crudos / (final.stem + '.png')
        trabajos.append({'id': m['comp'], 'props': props, 'frame': int(props['_dur'] * 30 * 0.62), 'salida': str(png)})
        por_id[str(png)] = final
    if not trabajos:
        print('nada que hacer')
        return
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump({'bundle': str(RM.bundle()), 'navegador': RM._chrome(), 'trabajos': trabajos}, f, ensure_ascii=False)
    mjs = AQUI.parent / 'remotion' / 'galeria.mjs'
    r = subprocess.run([RM._node(), str(mjs), f.name], cwd=str(mjs.parent), capture_output=True, text=True, encoding='utf-8', errors='replace')
    for linea in r.stdout.splitlines():
        if '"error"' in linea:
            print(linea[:240])
    from PIL import Image
    w, h = 216, 384
    fondo = Image.new('RGBA', (w, h))
    px = fondo.load()
    for y in range(h):                                   # degradado frío, como un plano de video oscuro
        for x in range(w):
            t = y / h
            px[x, y] = (int(38 + 22 * t), int(44 + 18 * t), int(58 + 10 * t), 255)
    hechos = 0
    for png, final in por_id.items():
        if not Path(png).exists():
            continue
        im = Image.open(png).convert('RGBA').resize((w, h), Image.LANCZOS)
        base = fondo.copy()
        base.alpha_composite(im)
        base.convert('RGB').save(final, quality=84, optimize=True)
        hechos += 1
    print('previas hechas:', hechos, 'de', len(trabajos), "->", destino)


if __name__ == '__main__':
    main()
