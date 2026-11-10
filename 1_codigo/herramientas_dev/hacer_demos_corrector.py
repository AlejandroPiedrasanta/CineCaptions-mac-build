# CineCaptions · By Cinema Productions
# 1_codigo/herramientas_dev/hacer_demos_corrector.py — los tres videos de ejemplo del Corrector sin audio (2_recursos/creativo).
"""
v5.78 (el usuario eligió la propuesta B: «mejora el ejemplo y da más ejemplos, ortografía, y que la página de Corrector pueda cambiar los colores y
tipografías»). Con el MISMO planificador y dibujo que el móvil del Corrector (vista_tema) y la foto de muestra del móvil, cada video enseña un
cambio hecho en el Corrector, tramo a tramo (cada tramo = el bloque entrando y quieto un momento):

    demo_principal.mp4   Estilo 2 · sin marcar sale «que nadie te CUENTA»  →  «nadie» como Principal: «con este truco que NADIE te cuenta»
    demo_ortografia.mp4  Estilo 2 · «Así ganamoz €10,000 en un mes»        →  corregida: «Así ganamos…»
    demo_colores.mp4     Estilo 1 · de fábrica → amarillo y Montserrat → violeta y serif → verde y Antagon (color y letra de la palabra grande)

Cada uno con su .jpg (el último tramo, quieto: «Reducir animaciones») y demo_corrector.json = {id: [inicio de cada tramo en s]}, que usa
editor_ui.DemoCorrector para que lo de encima de cada móvil (la palabra que se pinta, la corrección, el color elegido) vaya con el video.
360×780 (la proporción de la pantalla de movil.json), 30 fps, H.264 sin audio.

    python hacer_demos_corrector.py [--salida CARPETA]        (de fábrica: 2_recursos/creativo)
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent.parent                       # 1_codigo
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(AQUI))

ANCHO, ALTO, FPS = 360, 780, 30
QUIETO_S = 1.1                                                      # lo que se queda quieto cada tramo antes del siguiente
# v5.82 (el usuario: «que haga zoom a los captions para apreciar mejor el cambio»): cada video va ACERCADO a los captions con el mismo encuadre
# en todos sus tramos (el antes y el después se comparan en el mismo sitio y al mismo tamaño), como la cámara del móvil del Corrector
# (qt_kit.MarcoVista.poner_zoom_captions); los captions se rasterizan RASTER veces más finos para que acercados sigan nítidos
RASTER, ZOOM_MAX, LLENA = 2.0, 1.9, (0.92, 0.60)
BUENA = 'Así ganamos 10.000 euros en un mes con este truco que nadie te cuenta'.split()
MALA = 'Así ganamoz 10.000 euros en un mes con este truco que nadie te cuenta'.split()
NADIE = [('main' if w == 'nadie' else None) for w in BUENA]
# (id, pack, [(frase, roles, palabra del bloque, ajustes)])
DEMOS = (
    ('principal', 'Referencia', [(BUENA, [None] * len(BUENA), 'nadie', None), (BUENA, NADIE, 'nadie', None)]),
    ('ortografia', 'Referencia', [(MALA, [None] * len(MALA), 'ganamoz', None), (BUENA, [None] * len(BUENA), 'ganamos', None)]),
    ('colores', 'Kinetic', [(BUENA, NADIE, 'nadie', None),
                            (BUENA, NADIE, 'nadie', {'color_principal': '#FFD23F', 'fuente_principal': 'Montserrat|Black'}),
                            (BUENA, NADIE, 'nadie', {'color_principal': '#B388FF', 'fuente_principal': 'Instrument Serif|Regular'}),
                            (BUENA, NADIE, 'nadie', {'color_principal': '#24D18F', 'fuente_principal': 'Antagon|Regular'})]),
)


def _ffmpeg():
    ff = shutil.which('ffmpeg')
    if ff:
        return ff
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        raise SystemExit('No encuentro ffmpeg')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--salida', default=str(AQUI.parent / '2_recursos' / 'creativo'))
    salida = Path(ap.parse_args().salida)
    salida.mkdir(parents=True, exist_ok=True)
    import ajustes_ui
    ajustes_ui.guardar_prefs = lambda *a, **k: None
    import edicion_pro
    edicion_pro.emojis_permitidos = lambda *a, **k: False                 # (sin emojis: como GO sin la Edición PRO)
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QGuiApplication, QImage, QPainter
    app = QGuiApplication.instance() or QGuiApplication([])               # noqa: F841
    import vista_tema as VT

    def pintar(cu, t, camara, ruta=None):
        """El cuadro t (360×780) con la cámara (zoom, cx, cy en fracciones): guardado en `ruta` o devuelto."""
        img = QImage(ANCHO, ALTO, QImage.Format.Format_RGB888)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        z, cx, cy = camara
        p.translate(ANCHO / 2.0, ALTO / 2.0)
        p.scale(z, z)
        p.translate(-cx * ANCHO, -cy * ALTO)
        cu.pintar(p, QRectF(0, 0, ANCHO, ALTO), t)
        p.end()
        if ruta is None:
            return img
        img.save(str(ruta))

    def tinta(cu, k):
        """La caja (fracciones) de lo que SE VE de los captions del cue k (sin emoji), de sus capas (alfa > 10 %)."""
        import numpy as np
        ini = float(cu.cues[k].get('start') or 0.0)
        cajas = []
        for c in cu.capas:
            if c.get('tipo') == 'emoji' or abs(float(c.get('cue_t0', -99.0)) - ini) > 0.02:
                continue
            a = np.asarray(c['a'])[..., 0] > 0.1
            filas, cols = np.nonzero(a.any(axis=1))[0], np.nonzero(a.any(axis=0))[0]
            if len(filas) and len(cols):
                cajas.append((c['x'] + cols[0], c['y'] + filas[0], c['x'] + cols[-1] + 1, c['y'] + filas[-1] + 1))
        if not cajas:
            return None
        return (min(b[0] for b in cajas) / cu.ancho, min(b[1] for b in cajas) / cu.alto, max(b[2] for b in cajas) / cu.ancho,
                max(b[3] for b in cajas) / cu.alto)

    def camara(cajas):
        """El encuadre común de todos los tramos: la unión de sus cajas llenando LLENA, sin salirse de la foto."""
        cajas = [c for c in cajas if c]
        if not cajas:
            return 1.0, 0.5, 0.5
        x0, y0 = min(c[0] for c in cajas), min(c[1] for c in cajas)
        x1, y1 = max(c[2] for c in cajas), max(c[3] for c in cajas)
        z = min(ZOOM_MAX, max(1.0, min(LLENA[0] / max(1e-3, x1 - x0), LLENA[1] / max(1e-3, y1 - y0))))
        m = 0.5 / z
        return z, min(max((x0 + x1) / 2.0, m), 1.0 - m), min(max((y0 + y1) / 2.0, m), 1.0 - m)

    ff = _ffmpeg()
    tramos = {}
    for ident, pack, pasos in DEMOS:
        tmp = Path(tempfile.mkdtemp(prefix=f'cc_demo_{ident}_'))
        try:
            hechos = []
            for frase, roles, palabra, ajustes in pasos:
                palabras = [{'word': w, 'start': round(0.4 + i * 0.36, 3), 'end': round(0.4 + i * 0.36 + 0.32, 3)} for i, w in enumerate(frase)]
                estilo = dict(VT.estilo_de_pack(pack))
                if ajustes:
                    estilo['ajustes'] = ajustes
                cues = VT.planificar(palabras, roles, pack, estilo, idioma='es', fin_video=palabras[-1]['end'] + 1.0)
                cu = VT.Cuadros(cues, estilo, int(ANCHO * RASTER), int(ALTO * RASTER))
                k = cu.cue_de_palabra(palabra, palabras[frase.index(palabra)]['start'])
                hechos.append((cu, k))
            cam = camara([tinta(cu, k) for cu, k in hechos])
            n, inicios = 0, []
            for cu, k in hechos:
                a, _b = cu.tramo(k)
                quieto = cu.instante_quieto(k)
                inicios.append(round(n / FPS, 3))
                t = a
                while t < quieto:                                         # el bloque entrando…
                    pintar(cu, t, cam, tmp / f'{n:04d}.png')
                    n, t = n + 1, t + 1.0 / FPS
                for _ in range(int(QUIETO_S * FPS)):                      # …y quieto un momento
                    pintar(cu, quieto, cam, tmp / f'{n:04d}.png')
                    n += 1
                ultimo = pintar(cu, quieto, cam)
            ultimo.save(str(salida / f'demo_{ident}.jpg'), quality=90)
            print(f'{ident}: cámara zoom {cam[0]:.2f} centro ({cam[1]:.3f}, {cam[2]:.3f})', flush=True)
            subprocess.run([ff, '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', str(tmp / '%04d.png'), '-an', '-c:v', 'libx264',
                            '-pix_fmt', 'yuv420p', '-crf', '20', '-movflags', '+faststart', str(salida / f'demo_{ident}.mp4')], check=True)
            tramos[ident] = inicios
            print(f'{ident}: {len(pasos)} tramos {inicios}, {n} cuadros ({n / FPS:.1f} s)', flush=True)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    (salida / 'demo_corrector.json').write_text(json.dumps(tramos, indent=1) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
