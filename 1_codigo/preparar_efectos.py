# CineCaptions · By Cinema Productions
# 1_codigo/preparar_efectos.py — herramienta de desarrollo: convierte las imágenes de iconos sobre fondo blanco en SPRITES con transparencia (uno por icono).
"""
preparar_efectos.py  (v5.4.6)
-----------------------------
Las composiciones de iconos («PARA ACOMPAÑAR A LOS CAPTIONS (n).png») vienen sobre FONDO BLANCO. Para animarlas icono por icono hay que:

  1. pasar el blanco a transparencia (color-a-alfa: lo que en «Multiply» desaparece);
  2. separar los iconos: se agrupan los píxeles visibles que están cerca (los trozos de un mismo icono se funden con una dilatación);
  3. guardar cada icono recortado como PNG RGBA y un `pack.json` con su posición (fracciones del cuadro) y su tamaño.

    python preparar_efectos.py <carpeta con los PNG> [salida=2_recursos/efectos/iconos]

El resultado viaja con el programa (efectos_visuales.py lo anima y lo compone a la resolución del timeline). Solo hace falta repetirlo si se cambian las imágenes.
"""
import json
import sys
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

AQUI = Path(__file__).resolve().parent
UMBRAL_BLANCO = 246          # por encima de esto (canal mínimo) es fondo
ESCALA_ETIQUETAS = 6         # las agrupaciones se calculan a 1/6 de la imagen
RADIO_FUSION = 5             # (a esa escala) cuánto se agrandan los iconos para fundir sus trozos
SIN_RELLENO = {'pack1'}          # sin blancos que rellenar (arcos y destellos)
RADIOS = {'pack1': 2}         # (a esa escala) por pack: los destellos y los arcos son iconos distintos aunque estén cerca
MIN_AREA_PX = 900            # un grupo con menos píxeles visibles (a tamaño completo) se descarta (motas)
MARGEN = 14


def blanco_encerrado(arr):
    """Máscara (a tamaño completo) del blanco que queda ENCERRADO dentro de un icono (la X blanca de un botón rojo): ese blanco es del icono, no del fondo."""
    alto, ancho = arr.shape[:2]
    e = 3
    chica = np.asarray(Image.fromarray(arr).resize((ancho // e, alto // e), Image.Resampling.BOX)).min(axis=2)
    blanco = chica >= 244
    # sellar huecos finos de los contornos para que un interior casi cerrado cuente como encerrado
    sellado = dilatar(~blanco, 1)
    etiquetas, n = etiquetar(~sellado)
    toca_borde = set(np.unique(np.concatenate([etiquetas[0], etiquetas[-1], etiquetas[:, 0], etiquetas[:, -1]]))) - {0}
    dentro = (etiquetas > 0) & ~np.isin(etiquetas, list(toca_borde))
    # solo interiores de verdad (la X de un botón), no las motas de brillo: se descartan los pequeños
    grandes = np.zeros_like(dentro)
    for k in np.unique(etiquetas[dentro]):
        zona = etiquetas == k
        if int(zona.sum()) >= 20:
            grandes |= zona
    interior = dilatar(grandes, 1)
    completo = np.asarray(Image.fromarray((interior * 255).astype(np.uint8)).resize((ancho, alto), Image.Resampling.BILINEAR)) > 100
    return completo & (arr.min(axis=2) >= 205)         # a tamaño completo y solo donde de verdad es casi blanco: el borde sigue el contorno real


def a_alfa(arr, encerrado=None):
    """RGB sobre blanco -> RGBA: alfa = lo oscuro/saturado que es el píxel; color = el que daría ese alfa (sin el blanco)."""
    f = arr.astype(np.float32)
    minimo = f.min(axis=2)
    alfa = np.clip((255.0 - minimo) / 255.0, 0.0, 1.0)
    # estirar un poco: lo casi blanco es 0 y lo muy saturado ya es 1
    alfa = np.clip((alfa - 0.012) / 0.988, 0.0, 1.0)
    seguro = np.maximum(alfa, 1e-4)[..., None]
    color = np.clip((f - (1.0 - alfa)[..., None] * 255.0) / seguro, 0.0, 255.0)
    if encerrado is not None:
        alfa = np.where(encerrado, 1.0, alfa)
        color = np.where(encerrado[..., None], f, color)
    return np.dstack([color, (alfa * 255.0)[..., None]]).astype(np.uint8)


def etiquetar(mascara):
    """Componentes 8-conexas de una máscara booleana (BFS en Python; la máscara es pequeña)."""
    alto, ancho = mascara.shape
    etiquetas = np.zeros((alto, ancho), dtype=np.int32)
    n = 0
    for y0 in range(alto):
        for x0 in range(ancho):
            if mascara[y0, x0] and not etiquetas[y0, x0]:
                n += 1
                cola = deque([(y0, x0)])
                etiquetas[y0, x0] = n
                while cola:
                    y, x = cola.popleft()
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            yy, xx = y + dy, x + dx
                            if 0 <= yy < alto and 0 <= xx < ancho and mascara[yy, xx] and not etiquetas[yy, xx]:
                                etiquetas[yy, xx] = n
                                cola.append((yy, xx))
    return etiquetas, n


def dilatar(mascara, radio):
    img = Image.fromarray((mascara * 255).astype(np.uint8))
    img = img.filter(ImageFilter.MaxFilter(radio * 2 + 1))
    return np.asarray(img) > 0


def separar(ruta, salida, nombre):
    radio = RADIOS.get(nombre, RADIO_FUSION)
    arr = np.asarray(Image.open(ruta).convert('RGB'))
    alto, ancho = arr.shape[:2]
    rgba = a_alfa(arr, None if nombre in SIN_RELLENO else blanco_encerrado(arr))
    visible = rgba[..., 3] > 18
    pequena = np.asarray(Image.fromarray((visible * 255).astype(np.uint8)).resize((ancho // ESCALA_ETIQUETAS, alto // ESCALA_ETIQUETAS), Image.Resampling.BOX)) > 40
    etiquetas, n = etiquetar(dilatar(pequena, radio))
    carpeta = Path(salida) / nombre
    carpeta.mkdir(parents=True, exist_ok=True)
    sprites = []
    for k in range(1, n + 1):
        ys, xs = np.nonzero(etiquetas == k)
        x0, x1 = max(0, int(xs.min() * ESCALA_ETIQUETAS) - MARGEN), min(ancho, int((xs.max() + 1) * ESCALA_ETIQUETAS) + MARGEN)
        y0, y1 = max(0, int(ys.min() * ESCALA_ETIQUETAS) - MARGEN), min(alto, int((ys.max() + 1) * ESCALA_ETIQUETAS) + MARGEN)
        trozo = rgba[y0:y1, x0:x1].copy()
        # solo lo de ESTE grupo (la dilatación a baja resolución puede incluir un borde de otro)
        grupo = np.asarray(Image.fromarray(((etiquetas == k) * 255).astype(np.uint8)).resize((ancho, alto), Image.Resampling.NEAREST))[y0:y1, x0:x1] > 0
        trozo[..., 3] = np.where(grupo, trozo[..., 3], 0)
        if int((trozo[..., 3] > 18).sum()) < MIN_AREA_PX:
            continue
        # recorte final al contenido
        ys2, xs2 = np.nonzero(trozo[..., 3] > 6)
        ax0, ax1 = max(0, xs2.min() - MARGEN // 2), min(trozo.shape[1], xs2.max() + 1 + MARGEN // 2)
        ay0, ay1 = max(0, ys2.min() - MARGEN // 2), min(trozo.shape[0], ys2.max() + 1 + MARGEN // 2)
        trozo = trozo[ay0:ay1, ax0:ax1]
        gx0, gy0 = x0 + ax0, y0 + ay0
        archivo = f'{len(sprites) + 1:02d}.png'
        Image.fromarray(trozo, 'RGBA').save(carpeta / archivo, optimize=True)
        borde = [n for n, toca in (('izq', gx0 <= 2), ('der', gx0 + trozo.shape[1] >= ancho - 2), ('arriba', gy0 <= 2), ('abajo', gy0 + trozo.shape[0] >= alto - 2)) if toca]
        sprites.append({'archivo': archivo, 'borde': borde, 'cx': round((gx0 + trozo.shape[1] / 2) / ancho, 4), 'cy': round((gy0 + trozo.shape[0] / 2) / alto, 4),
                        'ancho': trozo.shape[1], 'alto': trozo.shape[0]})
    (carpeta / 'pack.json').write_text(json.dumps({'base': [ancho, alto], 'sprites': sprites}, indent=1), encoding='utf-8')
    return sprites


if __name__ == '__main__':
    origen = Path(sys.argv[1])
    salida = Path(sys.argv[2]) if len(sys.argv) > 2 else AQUI.parent / '2_recursos' / 'efectos' / 'iconos'
    for i, ruta in enumerate(sorted(origen.glob('PARA ACOMPA*.png')), 1):
        sprites = separar(ruta, salida, f'pack{i}')
        print(f'{ruta.name}: {len(sprites)} iconos ->', ', '.join(f"{s['archivo']}({s['cx']:.2f},{s['cy']:.2f} {s['ancho']}x{s['alto']})" for s in sprites))
