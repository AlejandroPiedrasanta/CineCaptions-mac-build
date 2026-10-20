# CineCaptions · By Cinema Productions
# 1_codigo/herramientas_dev/hacer_estilos_pro.py — v5.20: los EJEMPLOS de cada estilo de la página Efectos › Edición PRO (estilos_pro.SECCIONES):
# un clip 9:16 de 3 s por estilo (y el de «Automático») con las MISMAS piezas que pone GO (Remotion, OGraf, el efecto de la silueta) vestidas con
# estilos_pro._VESTIR, sobre el video de prueba de una persona. Salen en 2_recursos/edicion_pro/estilos_pro/<clave>_<id>.mp4 (+ .jpg, el póster).
#     python 1_codigo/herramientas_dev/hacer_estilos_pro.py [--solo pildora,detras] [--estilos neon,halo] [--rehacer]
# Tras cambiar un .tsx: `node empaquetar.mjs` en 1_codigo/remotion. Las piezas OGraf se pintan con el Chrome sin ventana del runtime de Remotion
# (como herramientas_dev/vista_ograf.py): cada fotograma en su iframe, todos en UNA captura con transparencia.
import argparse
import functools
import http.server
import json
import math
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
sys.path.insert(0, str(AQUI))
import hacer_ejemplos_pro as HP  # noqa: E402
import estilos_pro as EST  # noqa: E402
import edicion_pro_ograf as OG  # noqa: E402

W, H, FPS, DUR = 270, 480, 24, 3.2
HP.W, HP.H, HP.FPS, HP.DUR = W, H, FPS, DUR                   # las funciones de hacer_ejemplos_pro leen estos globales
HP.N = N = int(round(DUR * FPS))
TRAMOS = {'pildora': 51.9, 'detras': 15.6, 'gancho': 0.0, 'escenas': 56.0, 'kit': 43.6, 'graficos': 53.0, 'broll': 19.6, 'motions_completo': 28.6}
ACENTO_VIDEO = '#4C7DFF'                                         # «Automático»: el color que sacaría del video (para el ejemplo)
ICONOS3D = 'crown-dynamic-color,bell-dynamic-color,camera-dynamic-premium,calendar-dynamic-color'


# ----------------------------------------------------------------------------------------------------------------------- OGraf sin Resolve
UNO = """<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;width:%(W)dpx;height:%(H)dpx;overflow:hidden;background:transparent}
</style></head><body><script type="module">
import Pieza from './pieza.js';
customElements.define('cc-pieza', Pieza);
const el = document.createElement('cc-pieza'); document.body.appendChild(el);
const t = +new URLSearchParams(location.search).get('t');
await el.load({data: %(datos)s, renderCharacteristics: {resolution: {width: %(W)d, height: %(H)d}}});
await el.setActionsSchedule({schedule: [{timestamp: 0, action: {type: 'playAction'}}, {timestamp: %(stop)d, action: {type: 'stopAction'}}]});
await el.goToTime({timestamp: t * 1000});
</script></body></html>"""
COLS = 8


class _Callado(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def _chrome():
    raiz = AQUI.parent.parent / '2_recursos' / 'edicion_pro' / 'remotion' / 'runtime' / 'chrome'
    return next(iter(raiz.rglob('chrome-headless-shell.exe' if sys.platform == 'win32' else 'chrome-headless-shell')), None)


def ograf(pieza, valores, dur=DUR, desde=0.0):
    """Los N cuadros RGBA float (H, W, 4) de una pieza OGraf (None antes de `desde`)."""
    from PIL import Image
    tmp = Path(tempfile.mkdtemp(prefix='estilos_ograf_'))
    (tmp / 'pieza.js').write_text(OG.js_empaquetado(pieza), encoding='utf-8')
    vals = OG._normalizar(pieza, valores)
    for dentro, real in OG._archivos_de(pieza, vals):
        (tmp / dentro).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(real, tmp / dentro)
    (tmp / 'uno.html').write_text(UNO % {'W': W, 'H': H, 'datos': json.dumps(vals, ensure_ascii=False), 'stop': int(dur * 1000)}, encoding='utf-8')
    tiempos = [max(0.0, i / FPS - desde) for i in range(N)]
    filas = (N + COLS - 1) // COLS
    marcos = ''.join(f'<iframe src="uno.html?t={t:.4f}" style="position:absolute;left:{(i % COLS) * W}px;top:{(i // COLS) * H}px;width:{W}px;height:{H}px;'
                     f'border:0;background:transparent" allowtransparency="true"></iframe>' for i, t in enumerate(tiempos))
    (tmp / 'index.html').write_text(f'<!doctype html><html><head><meta charset="utf-8"><style>html,body{{margin:0;background:transparent}}</style></head>'
                                    f'<body>{marcos}</body></html>', encoding='utf-8')
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(_Callado, directory=str(tmp)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    png = tmp / 'hoja.png'
    try:
        subprocess.run([str(_chrome()), f'--screenshot={png}', f'--window-size={COLS * W},{filas * H}', '--hide-scrollbars', '--virtual-time-budget=20000',
                        '--force-device-scale-factor=1', '--default-background-color=00000000', '--allow-file-access-from-files',
                        f'http://127.0.0.1:{srv.server_port}/index.html'], capture_output=True, timeout=300)
    finally:
        srv.shutdown()
    if not png.exists():
        raise SystemExit(f'Chrome no pintó la pieza {pieza}')
    hoja = np.asarray(Image.open(png).convert('RGBA')).astype(np.float32) / 255.0
    out = []
    for i in range(N):
        if i / FPS < desde:
            out.append(None)
            continue
        c = hoja[(i // COLS) * H:(i // COLS + 1) * H, (i % COLS) * W:(i % COLS + 1) * W].copy()
        c[..., :3] = np.where(c[..., 3:4] > 1e-4, c[..., :3], 0.0)
        out.append(c)
    shutil.rmtree(tmp, ignore_errors=True)
    return out


def sobre(base, capa):
    """base RGB con una capa RGBA (Chrome y Remotion dan el color SIN premultiplicar)."""
    if capa is None:
        return base
    a = capa[..., 3:4]
    return base * (1.0 - a) + capa[..., :3] * a


def remotion(comp, props, dur, carpeta):
    return HP.remotion([('x', comp, props, dur)], carpeta).get('x') or []


# ----------------------------------------------------------------------------------------------------------------------- la silueta (detrás de ti)
def _mate_img(m):
    from PIL import Image
    return Image.fromarray((np.clip(m, 0, 1) * 255).astype(np.uint8), 'L')


def _ensancha(m, frac):
    from PIL import ImageFilter
    r = max(1, int(round(frac * W)))
    return np.asarray(_mate_img(m).filter(ImageFilter.MaxFilter(2 * r + 1))).astype(np.float32) / 255.0


def _difumina(m, frac):
    from PIL import ImageFilter
    return np.asarray(_mate_img(m).filter(ImageFilter.GaussianBlur(max(0.6, frac * W)))).astype(np.float32) / 255.0


def _rgb(h):
    h = str(h).lstrip('#')[:6]
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32) / 255.0


def con_efecto(img, persona_rgb, mate, ef):
    """Lo mismo que edicion_pro._fx_persona en Fusion: sombra de todo, resplandor, orillas (de fuera a dentro) y la persona encima."""
    capas = []                                                 # (alfa, color) de abajo arriba, sin la persona
    if ef and ef.get('brillo'):
        b = ef['brillo']
        a = _difumina(_ensancha(mate, b.get('ancho') or 0.0) if b.get('ancho') else mate, b.get('blur') or 0.02)
        capas.append((np.clip(a * float(b.get('fuerza') or 1.0), 0, 1), _rgb(b['color'])))
    for o in sorted((ef or {}).get('orillas') or [], key=lambda o: -o['ancho']):
        capas.append((_ensancha(mate, o['ancho']), _rgb(o['color'])))
    todo = mate.copy()
    for a, _c in capas:
        todo = np.maximum(todo, a)
    if ef and ef.get('sombra'):
        sh = ef['sombra']
        a = _difumina(todo, sh.get('blur') or 0.01) * float(sh.get('opacidad') or 0.6)
        a = np.roll(np.roll(a, int(round(-sh.get('dy', 0) * H)), axis=0), int(round(sh.get('dx', 0) * W)), axis=1)     # (dy, del alto: el Center de Fusion)
        img = img * (1.0 - a[..., None])
    for a, c in capas:
        img = img * (1.0 - a[..., None]) + c * a[..., None]
    return img * (1.0 - mate[..., None]) + persona_rgb * mate[..., None]


# ----------------------------------------------------------------------------------------------------------------------- un ejemplo
def _vestida(clave, v, pieza):
    """La pieza vestida con un estilo (v = None → Automático), con la misma función que usa GO."""
    if v is not None:
        EST._VESTIR[clave](pieza, v, EST.colores_de_variante(clave, v), {'t56': False, 'usuario': {}})
    return pieza


def hacer(clave, v, video, guion, carpeta, base_cache):
    t0 = TRAMOS[clave]
    if t0 not in base_cache:
        fr = HP.cuadros(video, t0)
        base_cache[t0] = (fr, [f.astype(np.float32) / 255.0 for f in fr], HP.palabras(guion, t0))
    fr, base, pal = base_cache[t0]
    out = []
    if clave == 'motions_completo':
        import av
        import motions_completo as MCO
        tramo = Path(carpeta) / 'tramo_mc.mp4'
        if not tramo.exists():
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
            if cur is None or a - cur['ini'] > 1.4:
                cur = {'ini': a, 'fin': a + 0.4, 'palabras': []}
                bl.append(cur)
            cur['palabras'].append({'texto': w, 't': round(a - cur['ini'], 3)})
            cur['fin'] = a + 0.45
        estilo = EST.props_motions_completo(v, EST.colores_de_variante(clave, v)) if v else {}
        mc = MCO.crear(bl, DUR, W, H, FPS, carpeta, 'es', {}, str(tramo), lambda t: None, ia=False, estilo=estilo)
        if not mc:
            raise SystemExit('Motions completo no salió')
        return [f / 255.0 for f in HP.cuadros(mc, 0.0)]
    if clave == 'detras':
        if 'mates' not in base_cache:
            base_cache['mates'] = HP.mates(fr)
        mates = base_cache['mates']
        ef = EST.efecto_persona(ident=v['id']) if v else None
        for i in range(N):
            t = i / FPS
            img = base[i]
            dichas = [(w, a) for w, a in pal if a <= t]
            if dichas:
                grupo = dichas[(len(dichas) - 1) // 2 * 2:]
                q = (t - grupo[-1][1]) / 0.2
                img = HP.sobre(img, HP.texto_rgba(HP._partir(' '.join(w for w, _a in grupo).upper(), 9), HP.LETRA_TIT, 118, 0.27,
                                                  escala=0.9 + 0.1 * HP._pop(q), alfa=min(1.0, 0.3 + q)))
            out.append(np.clip(con_efecto(img, base[i], mates[i], ef), 0, 1))
        return out
    capas_detras, capas_delante, cap_y, persona = [], [], 0.66, False
    if clave == 'pildora':
        p = _vestida(clave, v, {'remotion': 'AcompananteT5', 'valores': {'tipo': 'sticker', 'sticker': 'pizza', 'texto': 'Pizza', 'kicker': 'HOY COMEMOS',
                                                                          'y': 76, 'aspecto': 'cristal', 'acento': ACENTO_VIDEO, 'escala': 1.7}})
        capas_delante.append((remotion('AcompananteT5', p['valores'], DUR - 0.3, carpeta), 0.3))
        cap_y = 0.6
    elif clave == 'gancho':
        if 'mates' not in base_cache:
            base_cache['mates'] = HP.mates(fr)
        persona = True
        cx, cy = HP.cabeza(base_cache['mates'][int(FPS)])
        orb = {'imagenes': ICONOS3D, 'x': cx, 'y': cy, 'rx': 30, 'ry': 5, 'inclinacion': -8, 'vueltas': 0.3, 'escala': 1.0, 'acento': '#c9a46a'}
        tit = _vestida(clave, v, {'pieza': 'titular', 'valores': {'linea1': '¿VIVES O', 'linea2': 'ESTÁS DE PASO?', 'y': 30, 'x': 50, 'acento': '#ffd65c',
                                                                   'colorTexto': '#ffffff', 'fuente': 'serif'}})['valores']
        atras = _vestida(clave, v, {'pieza': 'orbita', 'valores': dict(orb, mitad='atras')})['valores']
        delante = _vestida(clave, v, {'pieza': 'orbita', 'valores': dict(orb, mitad='delante')})['valores']
        capas_detras += [(ograf('titular', tit), 0.0), (ograf('orbita', atras), 0.0)]
        capas_delante.append((ograf('orbita', delante), 0.0))
    elif clave == 'escenas':
        p = _vestida(clave, v, {'remotion': 'PictogramaE', 'valores': {'pose': 'trabajando', 'texto': 'EDITOR', 'sub': 'De 9 a 5', 'variante': 'oscuro',
                                                                        'acento': ACENTO_VIDEO}})
        capas_delante.append((remotion('PictogramaE', p['valores'], DUR - 0.4, carpeta), 0.4))
    elif clave == 'kit':
        p = _vestida(clave, v, {'remotion': 'ListaRazonesK', 'valores': {'items': 'Idea|Equipo|Clientes', 'n': 3, 'prefijo': 'RAZÓN', 'y': 46, 'tema': 'neon',
                                                                          'variante': 'pildora'}})
        t = _vestida(clave, v, {'remotion': 'TituloNeonK', 'valores': {'numero': '3', 'titulo': 'RAZONES', 'subtitulo': 'para empezar hoy', 'y': 20, 'tema': 'neon',
                                                                        'variante': 'neon'}})
        capas_delante += [(remotion('TituloNeonK', t['valores'], DUR - 0.2, carpeta), 0.2), (remotion('ListaRazonesK', p['valores'], DUR - 0.6, carpeta), 0.6)]
        cap_y = 0.74
    elif clave == 'graficos':
        cif = _vestida(clave, v, {'pieza': 'cifra', 'valores': {'numero': '300', 'unidad': '%', 'etiqueta': 'MÁS VENTAS', 'x': 50, 'y': 22}})['valores']
        lis = _vestida(clave, v, {'pieza': 'lista', 'valores': {'titulo': 'LO QUE NECESITAS', 'item1': 'Una idea', 'item2': 'Tu cámara', 'item3': 'Un guion',
                                                                 'x': 50, 'y': 66, 'tiempos': '0.4,0.7,0.95,1.2'}})['valores']
        capas_delante += [(ograf('cifra', cif, desde=0.15), 0.0), (ograf('lista', lis, desde=0.3), 0.0)]
        cap_y = None
    elif clave == 'broll':
        p = _vestida(clave, v, {'remotion': 'FotoE', 'valores': {'foto': HP.foto_data(HP.RAIZ / '2_recursos' / 'fondos_estilos' / 'fondo_03.jpg'),
                                                                  'palabra': 'EUROPA', 'variante': 'completa'}})
        capas_delante.append((remotion('FotoE', p['valores'], DUR - 0.5, carpeta), 0.5))
    mates = base_cache.get('mates') if persona else None
    for i in range(N):
        t = i / FPS
        img = base[i]
        for fr_capa, desde in capas_detras:
            img = sobre(img, HP.capa_en(fr_capa, i, desde) if desde else (fr_capa[i] if i < len(fr_capa) else None))
        if persona:
            a = mates[i][..., None]
            img = img * (1.0 - a) + base[i] * a
        if cap_y is not None and clave not in ('escenas', 'broll', 'gancho'):
            cap = HP.captions(pal, t, y=cap_y)
            if cap is not None:
                img = HP.sobre(img, cap)
        for fr_capa, desde in capas_delante:
            img = sobre(img, HP.capa_en(fr_capa, i, desde) if desde else (fr_capa[i] if i < len(fr_capa) else None))
        out.append(np.clip(img, 0.0, 1.0))
    return out


def guardar(frames, mp4, jpg):
    import av
    from PIL import Image
    mp4.parent.mkdir(parents=True, exist_ok=True)
    with av.open(str(mp4), 'w', options={'movflags': 'faststart'}) as o:
        s = o.add_stream('libx264', rate=FPS)
        s.width, s.height, s.pix_fmt = W, H, 'yuv420p'
        s.options = {'crf': '27', 'preset': 'slow'}
        for f in frames:
            for p in s.encode(av.VideoFrame.from_ndarray((f * 255).astype(np.uint8), format='rgb24')):
                o.mux(p)
        for p in s.encode():
            o.mux(p)
    Image.fromarray((frames[int(len(frames) * 0.6)] * 255).astype(np.uint8)).save(jpg, quality=84, optimize=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('video', nargs='?', default=str(HP.VIDEO))
    ap.add_argument('--guion', default=str(HP.GUION))
    ap.add_argument('--solo', default='')
    ap.add_argument('--estilos', default='')
    ap.add_argument('--rehacer', action='store_true')
    a = ap.parse_args()
    solo = [s for s in a.solo.split(',') if s]
    estilos = [s for s in a.estilos.split(',') if s]
    destino = EST.carpeta_previas()
    carpeta = Path(tempfile.mkdtemp(prefix='estilos_pro_'))
    for s in EST.SECCIONES:
        clave = s['clave']
        if solo and clave not in solo:
            continue
        cache = {}
        for v in [None] + list(s['variantes']):
            ident = v['id'] if v else 'auto'
            if estilos and ident not in estilos:
                continue
            mp4 = destino / f'{clave}_{ident}.mp4'
            if mp4.exists() and not a.rehacer:
                continue
            print('·', clave, ident, '…', flush=True)
            guardar(hacer(clave, v, a.video, a.guion, carpeta, cache), mp4, mp4.with_suffix('.jpg'))
            print('  ->', mp4.name, round(mp4.stat().st_size / 1024), 'KB', flush=True)


if __name__ == '__main__':
    main()
