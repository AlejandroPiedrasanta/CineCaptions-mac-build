# CineCaptions · By Cinema Productions
# 1_codigo/herramientas_dev/vista_ograf.py — ver una pieza OGraf SIN Resolve: la abre en el Chrome sin ventana del runtime de Remotion (servidor local)
# y saca fotogramas a varios tiempos sobre un fotograma de video, en una hoja. SOLO desarrollo (no entra en el .exe).
"""
    python 1_codigo/herramientas_dev/vista_ograf.py <pieza> '<valores json>' [--tiempos 0.2,0.6,1.2,2.5] [--ancho 1080 --alto 1920]
                                                   [--video <mp4 de fondo> --t-video 5] [--dur 4] [--salida hoja.png]
Cada tiempo es un goToTime() del componente (con su playAction en 0 y su stopAction al final de --dur), igual que lo pide Resolve.
"""
import argparse
import functools
import http.server
import json
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
import edicion_pro_ograf as OG  # noqa: E402

HTML = """<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;width:%(W)dpx;height:%(H)dpx;overflow:hidden;
background:#3b3f4a url('fondo.jpg') center/cover}</style></head><body><script type="module">
import Pieza from './pieza.js';
customElements.define('cc-pieza', Pieza);
const el = document.createElement('cc-pieza'); document.body.appendChild(el);
const q = new URLSearchParams(location.search), t = +q.get('t');
await el.load({data: %(datos)s, renderCharacteristics: {resolution: {width: %(W)d, height: %(H)d}}});
await el.setActionsSchedule({schedule: [{timestamp: 0, action: {type: 'playAction'}}, {timestamp: %(stop)d, action: {type: 'stopAction'}}]});
await el.goToTime({timestamp: t * 1000});
document.title = 'listo';
</script></body></html>"""


def _chrome():
    raiz = AQUI.parent.parent / '2_recursos' / 'edicion_pro' / 'remotion' / 'runtime' / 'chrome'
    return next(iter(raiz.rglob('chrome-headless-shell.exe' if sys.platform == 'win32' else 'chrome-headless-shell')), None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pieza')
    ap.add_argument('valores', nargs='?', default='{}')
    ap.add_argument('--tiempos', default='0.2,0.6,1.2,2.5')
    ap.add_argument('--ancho', type=int, default=1080)
    ap.add_argument('--alto', type=int, default=1920)
    ap.add_argument('--video', default='')
    ap.add_argument('--t-video', type=float, default=5.0)
    ap.add_argument('--dur', type=float, default=4.0)
    ap.add_argument('--salida', default='')
    a = ap.parse_args()
    W, H = a.ancho, a.alto
    tmp = Path(tempfile.mkdtemp(prefix='vista_ograf_'))
    (tmp / 'pieza.js').write_text(OG.js_empaquetado(a.pieza), encoding='utf-8')
    vals = OG._normalizar(a.pieza, json.loads(a.valores))
    for dentro, real in OG._archivos_de(a.pieza, vals):
        (tmp / dentro).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(real, tmp / dentro)
    from PIL import Image
    if a.video:
        import edicion_pro_persona as PE
        rgb = PE.fotograma(a.video, a.t_video)
        if rgb is not None:
            im = Image.fromarray(rgb)
            esc = max(W / im.width, H / im.height)
            im = im.resize((int(im.width * esc) + 1, int(im.height * esc) + 1))
            im.crop(((im.width - W) // 2, (im.height - H) // 2, (im.width - W) // 2 + W, (im.height - H) // 2 + H)).save(tmp / 'fondo.jpg', quality=88)
    (tmp / 'index.html').write_text(HTML % {'W': W, 'H': H, 'datos': json.dumps(vals, ensure_ascii=False), 'stop': int(a.dur * 1000)}, encoding='utf-8')
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(tmp)))
    srv.RequestHandlerClass.log_message = lambda *x: None
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    chrome = _chrome()
    if chrome is None:
        raise SystemExit('no encuentro chrome-headless-shell (2_recursos/edicion_pro/remotion/runtime/chrome)')
    cuadros = []
    for t in [float(x) for x in a.tiempos.split(',')]:
        png = tmp / f't{t:.2f}.png'
        subprocess.run([str(chrome), f'--screenshot={png}', f'--window-size={W},{H}', '--hide-scrollbars', '--virtual-time-budget=6000',
                        '--force-device-scale-factor=1', f'http://127.0.0.1:{srv.server_port}/index.html?t={t}'],
                       capture_output=True, timeout=120)
        if png.exists():
            cuadros.append(Image.open(png).convert('RGB'))
    srv.shutdown()
    if not cuadros:
        raise SystemExit('Chrome no sacó ningún fotograma')
    k = 360 / W
    hoja = Image.new('RGB', (int(W * k) * len(cuadros), int(H * k)), 'white')
    for i, c in enumerate(cuadros):
        hoja.paste(c.resize((int(W * k), int(H * k))), (i * int(W * k), 0))
    salida = Path(a.salida or tmp / 'hoja.png')
    hoja.save(salida)
    print('hoja:', salida)


if __name__ == '__main__':
    main()
