# CineCaptions · By Cinema Productions
# 1_codigo/hacer_previas_nuevas.py — herramienta de desarrollo: el ejemplo animado de CADA ajuste de la página «Efectos» que aún no lo tenía.
"""
hacer_previas_nuevas.py  (v5.4.20)
----------------------------------
La página «Efectos» enseña, para cada ajuste, un mp4 corto de 270×480 con el efecto YA puesto sobre una foto de muestra (como la intro, las transiciones y los iconos,
que hace hacer_previas_efectos.py). Este archivo hace el resto, con los MISMOS valores que usa la composición de Fusion (fusion_v1) y los mismos clips/secuencias que van a Resolve
(algo más exagerado el movimiento lento, para que se vea en 2 s):

    zoom_<nivel>            zoom lento del video                         temblor_<nivel>      temblor en los golpes de sonido
    fondo_<no|si>           fondo desenfocado en un video que no llena   saltos_<nivel>       zoom alterno en cada corte seco
    pausas_<nivel>          pausas quitadas (cortes secos + línea de tiempo)
    zoomintro_<nivel>       zoom que sube con el riser y se suelta en el destello de la intro
    cuantoscortes_<pocos|normal|todos>   cuántos cortes llevan transición
    numeros_si · pegatinas_si · enfasis_<subrayado|circulo> · alturaenfasis_<arriba|centro|abajo> · ambiente_<polvo|grano|luz> · fuerzaambiente_<nivel> · cierre_<cta|logo|final> · broll_si

    python hacer_previas_nuevas.py [salida=2_recursos/efectos/previas] [nombre_empieza_por …]

Solo hace falta repetirlo si cambian los efectos o su animación. El video no lleva texto propio (solo un texto de muestra donde el efecto lo necesita).
"""
import math
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import efectos_extra as X
import efectos_visuales as F
import fusion_v1 as FV
from hacer_previas_efectos import ALTO, ANCHO, FOTOS, _fotograma

FPS = 30
TOTAL = 72
LOGO = AQUI.parent / '2_recursos' / 'logo_cinema_productions.png'
NIVELES = ('suave', 'normal', 'fuerte')


# ----------------------------------------------------------------------------------------------------------------------- piezas
def _foto(k):
    return np.asarray(_fotograma(k))


def _zoom(arr, z, dx=0, dy=0):
    """El fotograma ampliado z veces desde el centro y movido (dx, dy) píxeles."""
    r = Image.fromarray(arr).resize((int(ANCHO * z + 0.5), int(ALTO * z + 0.5)), Image.Resampling.BILINEAR)
    x0 = max(0, min(r.width - ANCHO, (r.width - ANCHO) // 2 - int(dx)))
    y0 = max(0, min(r.height - ALTO, (r.height - ALTO) // 2 - int(dy)))
    return np.asarray(r.crop((x0, y0, x0 + ANCHO, y0 + ALTO)))


def _screen(base, capa, fuerza=1.0):
    a = base.astype(np.float32) / 255.0
    b = capa.astype(np.float32) / 255.0 * fuerza
    return (255.0 * (1.0 - (1.0 - a) * (1.0 - b))).astype(np.uint8)


def _destello(base, alfa):
    """Un fogonazo blanco de intensidad alfa (0…1) encima."""
    if alfa <= 0.01:
        return base
    return _screen(base, np.full(base.shape, 255, np.uint8), min(1.0, alfa))


def _componer(base, sec, k):
    """El fotograma k (1…n) de una secuencia de PNG con alpha encima de `base`."""
    if not sec or not (1 <= k <= sec['n']):
        return base
    try:
        cuadro = Image.open(sec['patron'] % k).convert('RGBA').resize((ANCHO, ALTO), Image.Resampling.LANCZOS)
    except Exception:
        return base
    fondo = Image.fromarray(base).convert('RGBA')
    fondo.alpha_composite(cuadro)
    return np.asarray(fondo.convert('RGB'))


def _texto(arr, texto, cy, tam=0.12, color=(255, 255, 255)):
    """Un texto de muestra (como un caption) centrado a la altura cy (fracción del alto), con sombra."""
    im = Image.fromarray(arr).convert('RGBA')
    cap = Image.new('RGBA', im.size, (0, 0, 0, 0))
    g = ImageDraw.Draw(cap)
    fuente = X._fuente(ANCHO * tam)
    caja = g.textbbox((0, 0), texto, font=fuente)
    x, y = (ANCHO - (caja[2] - caja[0])) / 2 - caja[0], ALTO * cy - (caja[3] - caja[1]) / 2 - caja[1]
    g.text((x + 3, y + 4), texto, font=fuente, fill=(0, 0, 0, 170))
    g.text((x, y), texto, font=fuente, fill=color + (255,))
    im.alpha_composite(cap)
    return np.asarray(im.convert('RGB'))


def _guardar(nombre, fotogramas, poster, salida):
    fotogramas = list(fotogramas)
    X._codificar_video(salida / f'{nombre}.mp4', iter(fotogramas), ANCHO, ALTO, fps=FPS, crf=24)
    Image.fromarray(fotogramas[min(poster, len(fotogramas) - 1)]).save(salida / f'{nombre}.jpg', quality=88)
    print('  ', nombre, len(fotogramas), 'fotogramas')


def _video(ruta, n_max=300):
    """Los fotogramas de un mp4 (a ANCHO×ALTO) como arrays RGB."""
    import av
    salida = []
    with av.open(str(ruta)) as c:
        for k, fr in enumerate(c.decode(video=0)):
            if k >= n_max:
                break
            salida.append(fr.reformat(width=ANCHO, height=ALTO, format='rgb24').to_ndarray())
    return salida


# ----------------------------------------------------------------------------------------------------------------------- movimiento
def previa_zoom(nivel, salida):
    A = _foto(1)
    k = FV.ZOOM_LENTO[nivel] * 2.0                      # el real tarda todo el video: aquí se ve en 2 s
    _guardar(f'zoom_{nivel}', [_zoom(A, 1.0 + k * min(1.0, f / (TOTAL - 14.0))) for f in range(TOTAL)], 40, salida)


def previa_temblor(nivel, salida):
    A = _foto(1)
    desp, pico = FV.TEMBLOR[nivel]
    desp, pico = desp * 1.6, pico * 1.6
    cuadros = []
    for f in range(TOTAL):
        env = 0.0
        for golpe in (10, 40):
            if f >= golpe:
                env = max(env, max(0.0, 1.0 - (f - golpe) / 11.0))
        z = 1.0 + 0.02 + pico * env
        cuadros.append(_zoom(A, z, desp * env * math.sin(f * 7.3) * ANCHO, desp * 0.8 * env * math.sin(f * 5.9 + 1.7) * ALTO))
    _guardar(f'temblor_{nivel}', cuadros, 12, salida)


def previa_fondo(si, salida):
    f = Image.open(F.carpeta_efectos().parent / 'fondos_estilos' / FOTOS[2]).convert('RGB')
    esc = ANCHO / f.width
    f = f.resize((ANCHO, int(f.height * esc)), Image.Resampling.LANCZOS)
    alto_h = int(ANCHO * 9 / 16)
    y0 = int(f.height * 0.38)
    banda = f.crop((0, y0, ANCHO, y0 + alto_h))                    # un video horizontal (16:9)
    cuadros = []
    for k in range(TOTAL):
        z = 1.0 + 0.05 * k / TOTAL
        b = banda.resize((int(ANCHO * z), int(alto_h * z)), Image.Resampling.BILINEAR)
        b = b.crop(((b.width - ANCHO) // 2, (b.height - alto_h) // 2, (b.width - ANCHO) // 2 + ANCHO, (b.height - alto_h) // 2 + alto_h))
        if si == 'si':
            fondo = banda.resize((int(ALTO * 16 / 9), ALTO), Image.Resampling.BILINEAR)
            fondo = fondo.crop(((fondo.width - ANCHO) // 2, 0, (fondo.width - ANCHO) // 2 + ANCHO, ALTO)).filter(ImageFilter.GaussianBlur(14))
            fondo = Image.eval(fondo, lambda v: int(v * 0.72))
        else:
            fondo = Image.new('RGB', (ANCHO, ALTO), (0, 0, 0))
        fondo.paste(b, (0, (ALTO - alto_h) // 2))
        cuadros.append(np.asarray(fondo))
    _guardar(f'fondo_{si}', cuadros, 30, salida)


# ----------------------------------------------------------------------------------------------------------------------- ritmo
def previa_saltos(nivel, salida):
    fotos = [_foto(1), _foto(2), _foto(1)]
    k = FV.ZOOM_SALTOS[nivel] * 1.5
    cuadros = []
    for f in range(TOTAL):
        tramo = min(2, f // 24)
        cuadros.append(_zoom(fotos[tramo], 1.0 + (k if tramo == 1 else 0.0) + 0.012 * (f % 24) / 24.0))
    _guardar(f'saltos_{nivel}', cuadros, 36, salida)


def previa_pausas(nivel, salida):
    """La misma toma con cortes secos donde estaba cada pausa y, debajo, la línea de tiempo con las pausas (rojo) que se van cerrando."""
    A = _foto(1)
    quitar = {'suave': 1, 'normal': 2, 'fuerte': 3}[nivel]
    rng = np.random.default_rng(4)
    # la línea: voz, pausa, voz, pausa… (anchos relativos)
    voces = [0.22, 0.18, 0.26, 0.20, 0.14]
    pausas = [0.07, 0.09, 0.06, 0.08]
    inicio_cierre = [14, 28, 42, 54]
    h_panel, margen = 66, 14
    alturas = [rng.uniform(0.35, 1.0, 14) for _ in range(len(voces))]
    cuadros = []
    saltos = 0
    for f in range(TOTAL):
        # cuánto de cada pausa queda (1 = entera, 0 = cerrada)
        resto = []
        for i in range(len(pausas)):
            if i < quitar:
                u = min(1.0, max(0.0, (f - inicio_cierre[i]) / 7.0))
                resto.append(1.0 - u)
            else:
                resto.append(1.0)
        # el video salta (corte seco) cuando una pausa se cierra
        saltos = sum(1 for i in range(quitar) if f >= inicio_cierre[i] + 7)
        base = _zoom(A, 1.0 + 0.045 * (saltos % 2) + 0.01 * saltos, dx=7 * ((-1) ** saltos) * min(1, saltos), dy=0)
        im = Image.fromarray(base).convert('RGBA')
        capa = Image.new('RGBA', im.size, (0, 0, 0, 0))
        g = ImageDraw.Draw(capa)
        y1 = ALTO - margen
        g.rounded_rectangle((margen, y1 - h_panel, ANCHO - margen, y1), radius=12, fill=(8, 14, 26, 205))
        total_w = sum(voces) + sum(p * r for p, r in zip(pausas, resto))
        x = margen + 10
        ancho_util = ANCHO - 2 * margen - 20
        for i, v in enumerate(voces):
            w = ancho_util * v / total_w
            n_b = max(2, int(w // 5))
            for j in range(n_b):
                a = alturas[i][j % len(alturas[i])]
                bx = x + j * (w / n_b)
                hb = (h_panel - 22) * (0.25 + 0.75 * a)
                g.rounded_rectangle((bx, y1 - h_panel / 2 - hb / 2, bx + max(2, w / n_b - 2), y1 - h_panel / 2 + hb / 2), radius=2, fill=(46, 230, 160, 255))
            x += w
            if i < len(pausas):
                wp = ancho_util * pausas[i] * resto[i] / total_w
                if wp > 0.6:
                    g.rounded_rectangle((x, y1 - h_panel / 2 - 2, x + wp, y1 - h_panel / 2 + 2), radius=2, fill=(235, 84, 96, 255))
                    # una marca de corte
                    if i < quitar and 0.05 < resto[i] < 0.95:
                        g.line((x + wp / 2, y1 - h_panel + 8, x + wp / 2, y1 - 8), fill=(255, 255, 255, 230), width=2)
                x += wp
        im.alpha_composite(capa)
        cuadros.append(np.asarray(im.convert('RGB')))
    _guardar(f'pausas_{nivel}', cuadros, 20, salida)


def previa_zoomintro(nivel, salida):
    A = _foto(0)
    k = FV.ZOOM_INTRO[nivel] * 1.6
    pico, suelta = 30, 13
    cuadros = []
    for f in range(TOTAL):
        if f < pico:
            z = 1.0 + k * (f / float(pico)) ** 1.7                  # sube con el riser
        else:
            z = 1.0 + k * max(0.0, 1.0 - (f - pico) / float(suelta)) ** 2                # y se suelta de golpe
        base = _zoom(A, z)
        alfa = 0.0 if f < pico - 2 else max(0.0, 0.95 - (f - (pico - 2)) / 11.0)
        cuadros.append(_destello(base, alfa))
    _guardar(f'zoomintro_{nivel}', cuadros, 26, salida)


def previa_cuantos_cortes(cuanto, salida):
    fotos = [_foto(0), _foto(1), _foto(2), _foto(0), _foto(1), _foto(2)]
    con = {'pocos': (3,), 'normal': (1, 3, 5), 'todos': (1, 2, 3, 4, 5)}[cuanto]
    cuadros = []
    for f in range(90):
        tramo = min(5, f // 15)
        base = _zoom(fotos[tramo], 1.0 + 0.02 * (f % 15) / 15.0)
        alfa = 0.0
        for b in con:
            d = abs(f - b * 15)
            alfa = max(alfa, max(0.0, 1.0 - d / 7.0) * 0.85)
        cuadros.append(_destello(base, alfa))
    _guardar(f'cuantoscortes_{cuanto}', cuadros, 15, salida)


# ----------------------------------------------------------------------------------------------------------------------- más efectos
def _zona():
    return [X.zona_captions(ANCHO, ALTO)]


def previa_numeros(salida):
    A = _foto(1)
    sec = X.secuencia_numero(1, ANCHO, ALTO, _zona(), 0)
    _guardar('numeros_si', [_componer(A, sec, f - 6 + 1) for f in range(TOTAL)], 24, salida)


def previa_pegatinas(salida):
    A = _foto(2)
    sec = X.secuencia_pegatina('money_bag', ANCHO, ALTO, _zona(), 0) or X.secuencia_pegatina('fire', ANCHO, ALTO, _zona(), 0)
    _guardar('pegatinas_si', [_componer(_texto(A, 'MONEY', 0.74, 0.12), sec, f - 6 + 1) for f in range(TOTAL + 6)], 26, salida)


def previa_enfasis(tipo, salida):
    A = _texto(_foto(1), 'THE BEST', 0.47 if tipo == 'subrayado' else 0.52, 0.15, (255, 255, 255))
    sec = X.secuencia_enfasis(tipo, ANCHO, ALTO, 'centro')
    _guardar(f'enfasis_{tipo}', [_componer(A, sec, f - 6 + 1) for f in range(TOTAL)], 32, salida)


def previa_ambiente(ident, salida):
    A = _foto(1)
    ruta = X.clip_overlay(ident, ANCHO, ALTO)
    capa = _video(ruta) if ruta else []
    fuerza = {'polvo': 0.95, 'grano': 0.95, 'luz': 0.85}.get(ident, 0.9)
    _guardar(f'ambiente_{ident}', [_screen(A, capa[f % len(capa)], fuerza) if capa else A for f in range(TOTAL)], 30, salida)


def previa_altura_enfasis(altura, salida):
    cy = X.ALTURAS[altura]
    A = _texto(_foto(1), 'THE BEST', cy - 0.05, 0.15)
    sec = X.secuencia_enfasis('subrayado', ANCHO, ALTO, altura)
    _guardar(f'alturaenfasis_{altura}', [_componer(A, sec, f - 6 + 1) for f in range(TOTAL)], 32, salida)


def previa_fuerza_ambiente(nivel, salida):
    A = _foto(1)
    capa = _video(X.clip_overlay('polvo', ANCHO, ALTO))
    fuerza = {'suave': 0.25, 'normal': 0.45, 'fuerte': 0.75}[nivel]                 # los valores reales de la página
    _guardar(f'fuerzaambiente_{nivel}', [_screen(A, capa[f % len(capa)], fuerza) for f in range(TOTAL)], 30, salida)


def previa_cierre(tipo, salida):
    A = _foto(0)
    sec = X.secuencia_outro(tipo, '', str(LOGO) if LOGO.is_file() else '', ANCHO, ALTO)
    n = sec['n'] if sec else TOTAL
    _guardar(f'cierre_{tipo}', [_componer(A, sec, f + 1) for f in range(n)], int(n * 0.55), salida)


def previa_broll(salida):
    A, B = _foto(1), _foto(2)
    cuadros = []
    for f in range(TOTAL):
        if 20 <= f < 52:
            base = _zoom(B, 1.0 + 0.06 * (f - 20) / 32.0)
        else:
            base = _zoom(A, 1.0 + 0.015 * f / TOTAL)
        alfa = max(0.0, 1.0 - abs(f - 20) / 4.0) * 0.5 + max(0.0, 1.0 - abs(f - 52) / 4.0) * 0.5
        base = _destello(base, alfa * 0.6)
        cuadros.append(_texto(base, 'LOOK AT THIS', 0.78, 0.095))
    _guardar('broll_si', cuadros, 36, salida)


# ----------------------------------------------------------------------------------------------------------------------- todo
def hacer_todo(salida, filtro=()):
    def quiere(nombre):
        return not filtro or any(nombre.startswith(p) for p in filtro)
    trabajos = []
    trabajos += [(f'zoom_{n}', lambda n=n: previa_zoom(n, salida)) for n in NIVELES]
    trabajos += [(f'temblor_{n}', lambda n=n: previa_temblor(n, salida)) for n in NIVELES]
    trabajos += [(f'fondo_{s}', lambda s=s: previa_fondo(s, salida)) for s in ('no', 'si')]
    trabajos += [(f'saltos_{n}', lambda n=n: previa_saltos(n, salida)) for n in NIVELES]
    trabajos += [(f'pausas_{n}', lambda n=n: previa_pausas(n, salida)) for n in NIVELES]
    trabajos += [(f'zoomintro_{n}', lambda n=n: previa_zoomintro(n, salida)) for n in NIVELES]
    trabajos += [(f'cuantoscortes_{c}', lambda c=c: previa_cuantos_cortes(c, salida)) for c in ('pocos', 'normal', 'todos')]
    trabajos += [('numeros_si', lambda: previa_numeros(salida)), ('pegatinas_si', lambda: previa_pegatinas(salida))]
    trabajos += [(f'enfasis_{t}', lambda t=t: previa_enfasis(t, salida)) for t in ('subrayado', 'circulo')]
    trabajos += [(f'ambiente_{o[0]}', lambda i=o[0]: previa_ambiente(i, salida)) for o in X.OVERLAYS]
    trabajos += [(f'cierre_{o[0]}', lambda i=o[0]: previa_cierre(i, salida)) for o in X.OUTROS]
    trabajos += [(f'alturaenfasis_{h}', lambda h=h: previa_altura_enfasis(h, salida)) for h in ('arriba', 'centro', 'abajo')]
    trabajos += [(f'fuerzaambiente_{n}', lambda n=n: previa_fuerza_ambiente(n, salida)) for n in NIVELES]
    trabajos += [('broll_si', lambda: previa_broll(salida))]
    hechos = 0
    for nombre, fn in trabajos:
        if quiere(nombre):
            fn()
            hechos += 1
    print('previas nuevas listas:', hechos, 'en', salida)


if __name__ == '__main__':
    salida = Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith('+') else F.carpeta_efectos() / 'previas'
    filtro = tuple(a.lstrip('+') for a in sys.argv[1:] if a.startswith('+'))
    salida.mkdir(parents=True, exist_ok=True)
    hacer_todo(salida, filtro)
