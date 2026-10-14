# CineCaptions · By Cinema Productions
# 1_codigo/herramientas_dev/generar_recortes.py — los «recortes de revista» del motion RecorteK (Kit8.tsx): de cada emoji 3D (Fluent, MIT) saca
# tres versiones en 2_recursos/edicion_pro/recortes/: trama (blanco y negro con puntos de imprenta y borde de papel RASGADO), color (sticker
# troquelado con borde blanco) y linea (contorno blanco para el neón; el color lo pone la animación). SOLO desarrollo: el resultado va al instalador.
"""python generar_recortes.py [ids…]     (sin ids: la lista RECORTES; rehace todo)"""
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

RAIZ = Path(__file__).resolve().parents[2]
ORIGEN = RAIZ / '2_recursos' / 'emojis' / 'png'
EXTRA = RAIZ / '2_recursos' / 'edicion_pro' / 'fluent_extra'      # v5.5.3: más Fluent 3D (MIT) bajados del repositorio de Microsoft
DESTINO = RAIZ / '2_recursos' / 'edicion_pro' / 'recortes'
LIENZO, DENTRO = 440, 330                     # lado del PNG y del dibujo (el resto: borde de papel y aire para la sombra)
PAPEL, TINTA = np.array([246, 244, 238.0]), np.array([20, 20, 22.0])

# Los conceptos que se pueden «recortar» (id de Fluent). edicion_pro_kit7.RECORTES dice qué palabras los llaman.
RECORTES = [
    'money_bag', 'dollar_banknote', 'money_with_wings', 'coin', 'credit_card', 'bank', 'receipt', 'light_bulb', 'brain', 'alarm_clock',
    'hourglass_not_done', 'calendar', 'trophy', '1st_place_medal', 'crown', 'red_exclamation_mark', 'double_exclamation_mark',
    'red_question_mark', 'exclamation_question_mark', 'megaphone', 'loudspeaker', 'pushpin', 'round_pushpin', 'chart_increasing',
    'chart_decreasing', 'bar_chart', 'bullseye', 'fire', 'red_heart', 'broken_heart', 'house', 'office_building', 'rocket', 'wrapped_gift',
    'camera', 'movie_camera', 'clapper_board', 'microphone', 'studio_microphone', 'musical_notes', 'headphone', 'airplane', 'world_map',
    'globe_showing_europe_africa', 'books', 'open_book', 'graduation_cap', 'briefcase', 'key', 'locked', 'unlocked', 'eyes',
    'magnifying_glass_tilted_left', 'gem_stone', 'check_mark_button', 'cross_mark', 'no_entry', 'prohibited', 'warning', 'hundred_points',
    'sparkles', 'glowing_star', 'star', 'laptop', 'mobile_phone', 'desktop_computer', 'keyboard', 'memo', 'pencil', 'writing_hand',
    'handshake', 'flexed_biceps', 'folded_hands', 'thumbs_up', 'thumbs_down', 'clapping_hands', 'raising_hands', 'index_pointing_up',
    'party_popper', 'confetti_ball', 'balloon', 'birthday_cake', 'rose', 'hot_beverage', 'pizza', 'hamburger', 'shopping_cart',
    'shopping_bags', 'package', 'delivery_truck', 'automobile', 'robot', 'gear', 'hammer_and_wrench', 'toolbox', 'chequered_flag',
    'skull', 'ghost', 'collision', 'exploding_head', 'thinking_face', 'face_screaming_in_fear', 'smiling_face_with_sunglasses',
    'money_mouth_face', 'nerd_face', 'face_with_tears_of_joy', 'pile_of_poo', 'seedling', 'potted_plant', 'sun', 'rainbow', 'dna',
    'microscope', 'pill', 'stethoscope', 'game_die', 'video_game', 'television', 'speech_balloon', 'thought_balloon', 'bell', 'battery',
    'electric_plug', 'compass', 'chocolate_bar', 'four_leaf_clover', 'teddy_bear', 'unicorn', 'lion', 'dog_face', 'cat_face', 'butterfly',
]


def _mascara(alfa):
    return Image.fromarray(np.clip(alfa * 255, 0, 255).astype('uint8'), 'L')


def _arr(im):
    return np.asarray(im, dtype=np.float32) / 255.0


def dilatar(alfa, px):
    """La silueta engordada `px` (suave): desenfoque + umbral bajo."""
    m = _mascara(alfa)
    for _ in range(max(1, px // 4)):
        m = m.filter(ImageFilter.MaxFilter(9))
    return _arr(m.filter(ImageFilter.GaussianBlur(2.2)))


def ruido_suave(lado, celdas, semilla):
    rng = np.random.default_rng(semilla)
    peq = Image.fromarray((rng.random((celdas, celdas)) * 255).astype('uint8'), 'L')
    return _arr(peq.resize((lado, lado), Image.BICUBIC)) * 2 - 1


def origen_de(nombre):
    for p in (ORIGEN / f'rcs_emoji_{nombre}.png', EXTRA / f'{nombre}.png'):
        if p.exists():
            return p
    return None


def cargar(nombre):
    im = Image.open(origen_de(nombre)).convert('RGBA')
    im = im.crop(im.getchannel('A').point(lambda v: 255 if v > 8 else 0).getbbox())
    k = DENTRO / max(im.size)
    im = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)
    lienzo = Image.new('RGBA', (LIENZO, LIENZO), (0, 0, 0, 0))
    lienzo.paste(im, ((LIENZO - im.width) // 2, (LIENZO - im.height) // 2), im)
    a = np.asarray(lienzo, dtype=np.float32) / 255.0
    return a[..., :3], a[..., 3]


def trama(rgb, alfa, semilla):
    """Blanco y negro con puntos de imprenta (45°), sobre papel con el borde RASGADO."""
    lum = rgb @ np.array([0.299, 0.587, 0.114])
    dentro = alfa > 0.5
    lo, hi = np.percentile(lum[dentro], 3), np.percentile(lum[dentro], 97)
    lum = np.clip((lum - lo) / max(1e-3, hi - lo), 0, 1) ** 1.15
    suave = _arr(_mascara(lum).filter(ImageFilter.GaussianBlur(2.0)))
    paso = 6.5
    y, x = np.mgrid[0:LIENZO, 0:LIENZO].astype(np.float32)
    u, v = (x + y) / math.sqrt(2), (y - x) / math.sqrt(2)
    fu, fv = (u % paso) - paso / 2, (v % paso) - paso / 2
    d = np.sqrt(fu * fu + fv * fv)
    oscuro = 1 - suave
    r = paso * 0.74 * np.sqrt(oscuro)
    tinta = np.clip(r - d + 0.5, 0, 1)
    tinta = np.maximum(tinta, np.clip((oscuro - 0.86) * 8, 0, 1))          # las sombras profundas, tinta llena
    tinta *= alfa
    borde = dilatar(alfa, 18) + 0.22 * ruido_suave(LIENZO, 22, semilla) + 0.08 * ruido_suave(LIENZO, 90, semilla + 1)
    borde = _arr(_mascara(np.clip((borde - 0.5) * 6 + 0.5, 0, 1)).filter(ImageFilter.GaussianBlur(0.6)))
    grano = 1 + 0.025 * ruido_suave(LIENZO, 200, semilla + 2)[..., None]
    color = (PAPEL * (1 - tinta[..., None]) + TINTA * tinta[..., None]) * grano
    return np.dstack([np.clip(color, 0, 255), np.maximum(borde, alfa) * 255])


def color(rgb, alfa):
    """El sticker a color con borde blanco troquelado (liso)."""
    borde = dilatar(alfa, 16)
    borde = _arr(_mascara(np.clip((borde - 0.45) * 5, 0, 1)).filter(ImageFilter.GaussianBlur(0.7)))
    base = rgb * alfa[..., None] + (1 - alfa[..., None])                   # el emoji sobre blanco
    return np.dstack([np.clip(base * 255, 0, 255), np.maximum(borde, alfa) * 255])


def linea(rgb, alfa):
    """Contorno blanco (silueta + los bordes fuertes de dentro) para pintarlo de neón."""
    fuera = dilatar(alfa, 5)
    nucleo = _arr(_mascara(alfa).filter(ImageFilter.MinFilter(7)))
    anillo = np.clip(fuera - nucleo, 0, 1) * (fuera > 0.3)
    lum = _arr(_mascara(rgb @ np.array([0.299, 0.587, 0.114])).filter(ImageFilter.GaussianBlur(1.4)))
    gy, gx = np.gradient(lum)
    mag = np.sqrt(gx * gx + gy * gy) * _arr(_mascara(alfa).filter(ImageFilter.MinFilter(13)))
    umbral = np.percentile(mag[alfa > 0.5], 93) if (alfa > 0.5).any() else 1
    dentro = np.clip((mag - umbral) / max(1e-4, umbral), 0, 1)
    trazo = _arr(_mascara(np.maximum(anillo, dentro * 0.9)).filter(ImageFilter.GaussianBlur(0.8)))
    return np.dstack([np.full(alfa.shape + (3,), 255.0), np.clip(trazo * 1.4, 0, 1) * 255])


def guardar(arr, ruta):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr.astype('uint8'), 'RGBA').save(ruta, 'WEBP', quality=90, alpha_quality=100, method=6)


def main():
    """Sin ids: la lista RECORTES + todos los de fluent_extra, saltando los que ya están hechos. El índice se rehace con lo que haya."""
    ids = sys.argv[1:] or list(dict.fromkeys(RECORTES + sorted(p.stem for p in EXTRA.glob('*.png'))))
    hechos = []
    for i, nombre in enumerate(ids):
        if origen_de(nombre) is None:
            print('  falta', nombre)
            continue
        if not sys.argv[1:] and all((DESTINO / v / f'{nombre}.webp').exists() for v in ('trama', 'color', 'linea')):
            continue
        rgb, alfa = cargar(nombre)
        guardar(trama(rgb, alfa, 100 + i), DESTINO / 'trama' / f'{nombre}.webp')
        guardar(color(rgb, alfa), DESTINO / 'color' / f'{nombre}.webp')
        guardar(linea(rgb, alfa), DESTINO / 'linea' / f'{nombre}.webp')
        hechos.append(nombre)
    todos = sorted(p.stem for p in (DESTINO / 'trama').glob('*.webp') if all((DESTINO / v / p.name).exists() for v in ('color', 'linea')))
    (DESTINO / 'indice.json').write_text(json.dumps(todos, ensure_ascii=False), encoding='utf-8')
    (DESTINO / 'LICENCIA.txt').write_text(
        'Recortes de CineCaptions: derivados de Fluent Emoji (estilo 3D) de Microsoft, licencia MIT\n'
        'https://github.com/microsoft/fluentui-emoji — Copyright (c) Microsoft Corporation.\n'
        'Tratamiento (trama de puntos, borde de papel, contorno): generar_recortes.py de CineCaptions.\n', encoding='utf-8')
    print(len(hechos), 'recortes nuevos ·', len(todos), 'en total')


if __name__ == '__main__':
    main()
