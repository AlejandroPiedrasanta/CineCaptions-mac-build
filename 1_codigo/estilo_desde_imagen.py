# CineCaptions · By Cinema Productions
# 1_codigo/estilo_desde_imagen.py — «Estilo desde una imagen»: lee un fotograma de un video viral y arma un pack con sus colores, su peso y su posición.
"""
Arrastras (eliges) un fotograma de un video con subtítulos que te gustan y el programa:

  1. busca el TEXTO (píxeles muy claros y poco saturados = blanco; muy saturados y claros = el color de acento),
  2. saca el color de acento (el tono más presente entre los saturados), el color base, qué tan GRUESAS son las letras
     (cuánto del texto sobrevive a erosionarlo) y si el texto va arriba o abajo,
  3. arma un pack nuevo de 3 variantes (el estilo de la imagen, otro acento y una versión editorial) con el MISMO generador
     que los packs Viral (la palabra principal con Luxe Shine) y lo deja en tu carpeta de packs, listo para elegir.

No reconoce la tipografía exacta (eso no se puede saber desde una imagen): usa las que ya viajan con el programa y acerca el
peso. Todo lo que sale se puede retocar con «Crea tu estilo».
"""
import colorsys
import copy
import json
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

import plantillas


def _slug(texto):
    t = unicodedata.normalize('NFKD', str(texto)).encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'[^A-Za-z0-9]+', '_', t).strip('_').lower() or 'estilo'


def analizar(ruta):
    """{'acento': (r,g,b), 'acento2': (r,g,b), 'base': (r,g,b), 'peso': 'Black'|..., 'pack': 'superior'|'inferior', 'texto_visto': bool}"""
    im = Image.open(ruta).convert('RGB')
    im.thumbnail((420, 420))
    a = np.asarray(im).astype(np.float32) / 255.0
    lum = a @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    mx, mn = a.max(axis=2), a.min(axis=2)
    sat = (mx - mn) / (mx + 1e-6)
    blanco = (lum > 0.86) & (sat < 0.20)
    vivo = (sat > 0.55) & (mx > 0.62)
    total = float(lum.size)
    # --- acento: el tono mas presente entre los pixeles vivos
    acento, acento2 = None, None
    if vivo.sum() > total * 0.0015:
        r, g, b = a[..., 0][vivo], a[..., 1][vivo], a[..., 2][vivo]
        h = np.array([colorsys.rgb_to_hsv(float(x), float(y), float(z))[0] for x, y, z in zip(r[::3], g[::3], b[::3])])
        hist, bordes = np.histogram(h, bins=36, range=(0.0, 1.0), weights=sat[vivo][::3])
        orden = np.argsort(hist)[::-1]
        def color_del_bin(k):
            m = (h >= bordes[k] - 0.03) & (h <= bordes[k + 1] + 0.03)
            if not m.any():
                return None
            c = np.array([r[::3][m].mean(), g[::3][m].mean(), b[::3][m].mean()])
            hh, ss, vv = colorsys.rgb_to_hsv(*c)
            return tuple(float(x) for x in colorsys.hsv_to_rgb(hh, min(1.0, max(ss, 0.7)), 1.0))
        acento = color_del_bin(int(orden[0]))
        for k in orden[1:]:
            if abs(((bordes[k] - bordes[orden[0]]) + 0.5) % 1.0 - 0.5) > 0.12 and hist[k] > hist[orden[0]] * 0.15:
                acento2 = color_del_bin(int(k))
                break
    if acento is None:
        acento = (1.0, 0.80, 0.22)
    if acento2 is None:
        hh, ss, vv = colorsys.rgb_to_hsv(*acento)
        acento2 = tuple(float(x) for x in colorsys.hsv_to_rgb((hh + 0.5) % 1.0, 0.75, 1.0))     # el complementario
    # --- color base de las letras normales: blanco puro o crema, segun lo que haya
    base = (1.0, 1.0, 1.0)
    if blanco.sum() > total * 0.0008:
        m = a[blanco]
        base = tuple(float(x) for x in np.clip(m.mean(axis=0) * 1.04, 0.0, 1.0))
        if min(base) > 0.93:
            base = (1.0, 1.0, 1.0)
    # --- grosor de las letras: cuanto del texto sobrevive a una erosion
    mascara = Image.fromarray(((blanco | vivo) * 255).astype(np.uint8))
    erosion = mascara.filter(ImageFilter.MinFilter(5))
    n0 = int(np.count_nonzero(np.asarray(mascara)))
    n1 = int(np.count_nonzero(np.asarray(erosion)))
    fraccion = (n1 / n0) if n0 else 0.3
    peso = 'Black' if fraccion > 0.42 else 'ExtraBold' if fraccion > 0.30 else 'Bold' if fraccion > 0.18 else 'SemiBold'
    # --- arriba o abajo: donde se concentra el texto
    filas = np.asarray(mascara).astype(np.float32).sum(axis=1)
    y_texto = float((filas * np.arange(len(filas))).sum() / filas.sum() / len(filas)) if filas.sum() > 0 else 0.7
    return {'acento': acento, 'acento2': acento2, 'base': base, 'peso': peso, 'fraccion_grueso': round(fraccion, 3),
            'pack': 'superior' if y_texto < 0.5 else 'inferior', 'y_texto': round(y_texto, 3), 'texto_visto': n0 > total * 0.002}


def _combinaciones(info, g):
    """Las 3 variantes del pack a partir de lo medido (copias de las del generador, retocadas)."""
    base1 = copy.deepcopy(g.COMBINACIONES[1])
    peso = info['peso']
    suave = 'Bold' if peso in ('Black', 'ExtraBold') else 'SemiBold'
    v1 = copy.deepcopy(base1)
    v1['nombre'] = 'Tu imagen'
    for rol in ('context', 'complement'):
        v1[rol]['color'] = info['base']
        v1[rol]['f2'] = ('Montserrat', suave)
    v1['main'].update(f1=('Montserrat', peso), f2=('Montserrat', peso), color=info['acento'])
    v1['entrada'] = 'pop'
    v2 = copy.deepcopy(v1)
    v2['nombre'] = 'Otro acento'
    v2['main']['color'] = info['acento2']
    v2['entrada'] = 'sube'
    v3 = copy.deepcopy(g.COMBINACIONES[3])
    v3['nombre'] = 'Editorial'
    v3['main']['color'] = info['acento']
    for rol in ('context', 'complement'):
        v3[rol]['color'] = info['base']
    return {1: v1, 2: v2, 3: v3}


def crear_pack(ruta_imagen, nombre=None):
    """Arma el pack en la carpeta de packs del usuario y devuelve (nombre, carpeta, info). Lanza si no hay contenedor o falla el generador."""
    info = analizar(ruta_imagen)
    nombre = (nombre or ('Estilo ' + Path(ruta_imagen).stem))[:40].strip()
    incluidas = plantillas.carpeta_incluida()
    if incluidas is None:
        raise RuntimeError('no encuentro los packs incluidos')
    n_cont = 'Viral Superior' if info['pack'] == 'superior' else 'Viral Inferior'
    contenedor = incluidas / n_cont / f'{n_cont} vertical.drb'
    if not contenedor.is_file():
        raise RuntimeError(f'falta {contenedor.name}')
    generador = incluidas.parent / 'generador_packs'
    if str(generador) not in sys.path:
        sys.path.insert(0, str(generador))
    import generar_comps as g
    import construir_pack as C
    carpeta = plantillas.carpeta_de_packs() / _slug(nombre)
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / f'{nombre} vertical.drb'
    guardadas = {k: g.COMBINACIONES[k] for k in (1, 2, 3)}
    try:
        g.COMBINACIONES.update(_combinaciones(info, g))
        C.construir(str(contenedor), str(destino), f'{nombre} vertical', info['pack'])
    finally:
        g.COMBINACIONES.update(guardadas)
    try:
        import packs_drt
        pos = packs_drt.posiciones_de_drb(str(destino))
        (carpeta / f'{nombre} vertical.posiciones.json').write_text(
            json.dumps({'origen': destino.name, 'clips': {k: list(v) for k, v in pos.items()}}, indent=1), encoding='utf-8')
    except Exception:
        pass
    (carpeta / 'pack.json').write_text(json.dumps({'version': 2, 'nombre': nombre, 'formatos': {'v': {'drb': destino.name}}},
                                                  ensure_ascii=False, indent=2), encoding='utf-8')
    try:
        plantillas.invalidar_packs()
    except Exception:
        pass
    return nombre, carpeta, info
