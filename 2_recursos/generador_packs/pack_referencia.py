# CineCaptions · By Cinema Productions
# 2_recursos/generador_packs/pack_referencia.py — arma el pack «Referencia»: 8 estilos de principal (Luxe Shine y presets de Amro) con las líneas pequeñas en dos pesos.
"""
El pack «Referencia» es el estilo de los captions virales de la referencia del usuario (REFERENCIA.mp4):

    arriba  = línea pequeña FINA   (Poppins Light, blanca)         -> las palabras normales de la frase
    abajo   = línea pequeña NEGRITA (Poppins Bold, blanca)         -> las palabras que se destacan dentro de la frase
    principal n = la palabra grande, un estilo distinto por variante:
        1 Impacto cian (azul degradado, pesado)      5 Editorial azul (serif cursiva azul)
        2 Editorial rosa (serif cursiva rosa)        6 Amro Fire (rojo fuego)
        3 Amro Highlight naranja (pastilla dorada)   7 Amro Strike rojo (tachado)
        4 Moderno blanco (negrita blanca)            8 Amro Underline lima (subrayado verde)
    v5.5 — variantes del BARRIDO DE LUZ de los cuatro estilos Luxe (1, 2, 4 y 5): el original (sutil, realza el brillo) y
        9-12  «Screen»: una banda de luz de color que se suma al texto (se ve claramente)
        13-16 «Sólido»: una banda opaca de color que tapa las letras a su paso
    El planificador (guion_planificador.py) las va alternando, así cada palabra grande no repite barrido ni color.
    v5.48 — Shine y Slide salen del Luxe Title Pack v1.09; sin las variantes de QUITAR (4, 11, 15). 17 «Count naranja»: macro Luxe Count para los
    números (cuenta de 0 a la cifra; prefijo de moneda, «%» y decimales salen del texto del clip).

Todos los clips van CENTRADOS en el cuadro (Tilt 0): la posición de cada palabra la pone el script (Pan/Tilt por línea, estilo «guion»).
Uso:  python pack_referencia.py [<carpeta de salida>]
"""
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(AQUI, '..', '..', '1_codigo'))
import generar_comps as g
import construir_pack as C

BLANCO = (1.0, 1.0, 1.0)
AZUL = (0.36, 0.62, 0.96)
ROSA = (1.0, 0.46, 0.70)
CIAN = (0.30, 0.58, 0.96)


# v5.48 (pedido: «junta un poco las letras»): Character Spacing de todos los textos Luxe del pack (antes 1,0 las pequeñas y 0,99 las grandes)
ESPACIADO = 0.99                     # (se probó 0,95: el usuario prefiere 0,99)


def _rol(fuente, tam, color=BLANCO, mayus=False, esp=ESPACIADO, retardo=0):
    return dict(f1=fuente, f2=fuente, tam=tam, esp=esp, mayus=mayus, color=color, retardo=retardo)


# tamaños iniciales (fracción del «Size» de Fusion); se afinan midiendo el render contra la referencia (ver AFINADO en el JSON del pack)
TAM_FINA, TAM_NEGRITA = 0.118, 0.118          # ~75 px a 1080 de ancho (medido en la referencia)
FINA = _rol(('Poppins', 'Light'), TAM_FINA)
NEGRITA = _rol(('Poppins', 'Bold'), TAM_NEGRITA)

AMRO = 'Amro principales.drb'
# entrada y salida del macro en segundos. v5.48: 0,14/0,10 -> 0,28/0,22, el deslizado con desenfoque de las referencias nuevas del usuario (ya no hay
# riesgo de que una palabra corta no se vea: luxe_macro limita la entrada y la salida al 30 % de lo que dura cada clip)
ANIM = (0.28, 0.22)
# v5.48 (pedido del usuario): variantes que ya no van en el pack; las demás conservan su número (los proyectos guardados no cambian de estilo).
QUITAR = (4, 11, 15)          # «Moderno blanco» y sus dos barridos
NARANJA = (1.0, 0.62, 0.20)
VARIANTE_COUNT = 17           # los números: macro Luxe Count (el planificador la elige para las cifras; no entra en la rotación)
# el barrido de fábrica tarda 1,75 s en acabar y las palabras grandes se ven ~0,55 s: aquí empieza enseguida y dura 0,40 s (el script de Resolve lo ajusta a cada palabra)
BARRIDO_BRILLO = {'modo': 'brillo', 'inicio': 0.06, 'largo': 0.40}
# (estilo base, color de la banda 'screen', color de la banda 'sólido'): cada variante lleva un color DISTINTO al del texto para que el barrido se note
VARIANTES_BARRIDO = ((1, (1.00, 0.86, 0.50), (1.00, 1.00, 1.00)),     # Impacto cian: luz dorada / banda blanca
                     (2, (1.00, 1.00, 1.00), (1.00, 0.93, 0.62)),     # Editorial rosa: luz blanca / banda oro pálido
                     (4, (0.55, 0.90, 1.00), (1.00, 0.55, 0.78)),     # Moderno blanco: luz azul hielo / banda rosa
                     (5, (1.00, 0.82, 0.92), (0.60, 1.00, 0.88)))     # Editorial azul: luz rosada / banda aguamarina


def _combo(nombre, main, amro=None, entrada='pop', barrido=None):
    # deslizar: las líneas pequeñas (Luxe Slide, Poppins Light / Bold) entran y salen hacia la derecha, sin «Mirror Out» (v5.48, pedido del usuario)
    c = {'nombre': nombre, 'context': dict(FINA), 'main': main, 'complement': dict(NEGRITA), 'entrada': entrada, 'luxe': True, 'mayus_real': True,
         'anim': ANIM, 'deslizar': 'derecha'}
    if barrido is not None and not amro:
        c['barrido'] = barrido
    if amro:
        c['rel'] = (0.0836, 0.0847)
        c['principal_drb'] = {'drb': amro[0], 'clip': 'principal' if amro[1] == 1 else f'principal {amro[1]}'}
    return c


def combinaciones(ruta_amro):
    base = [
        _combo('Impacto cian', _rol(('Poppins', 'ExtraBold'), 0.257, CIAN, mayus=True, esp=ESPACIADO), barrido=BARRIDO_BRILLO),
        _combo('Editorial rosa', _rol(('DM Serif Text', 'Italic'), 0.28, ROSA, esp=ESPACIADO), entrada='abre', barrido=BARRIDO_BRILLO),
        _combo('Amro Highlight naranja', _rol(('Inter', 'Black'), 0.17, (1.0, 0.55, 0.15), mayus=True), amro=(ruta_amro, 1)),
        _combo('Moderno blanco', _rol(('Poppins', 'Bold'), 0.18, BLANCO, esp=ESPACIADO), entrada='sube', barrido=BARRIDO_BRILLO),
        _combo('Editorial azul', _rol(('DM Serif Text', 'Italic'), 0.28, AZUL, esp=ESPACIADO), entrada='abre', barrido=BARRIDO_BRILLO),
        _combo('Amro Fire', _rol(('Inter', 'Black'), 0.17, (1.0, 0.30, 0.15), mayus=True), amro=(ruta_amro, 5)),
        _combo('Amro Strike rojo', _rol(('Inter', 'Black'), 0.17, (1.0, 0.28, 0.28), mayus=True), amro=(ruta_amro, 6)),
        _combo('Amro Underline lima', _rol(('Inter', 'Black'), 0.17, (0.62, 1.0, 0.30), mayus=True), amro=(ruta_amro, 3)),
    ]
    # 9-12 «Screen» y 13-16 «Sólido»: el mismo texto de los estilos 1, 2, 4 y 5 con otra forma y otro color de barrido
    screen, solido = [], []
    for n, c_screen, c_solido in VARIANTES_BARRIDO:
        b = base[n - 1]
        for lista, modo, color, etiqueta in ((screen, 'screen', c_screen, 'Screen'), (solido, 'solido', c_solido, 'Sólido')):
            lista.append(dict(b, nombre=f"{b['nombre']} · {etiqueta}", barrido={'modo': modo, 'inicio': 0.06, 'largo': 0.40, 'ancho': 0.09, 'color': color, 'mezcla': 1.0}))
    count = dict(_combo('Count naranja', _rol(('Poppins', 'ExtraBold'), 0.257, NARANJA, esp=ESPACIADO)), count=True)
    return base + screen + solido + [count]          # (el Count es la 17)


def construir(carpeta_salida, nombre='Referencia', contenedor=None, ruta_amro=None):
    """Genera <carpeta_salida>/<nombre> vertical.drb (+ .variantes.json, pack.json y .posiciones.json). Devuelve la ruta del .drb."""
    import plantillas
    incluidas = plantillas.carpeta_incluida()
    contenedor = contenedor or str(incluidas / 'Viral Superior' / 'Viral Superior vertical.drb')
    ruta_amro = ruta_amro or str(incluidas.parent / 'guia_estilo' / 'Amro principales.drb')
    combos = combinaciones(ruta_amro)
    os.makedirs(carpeta_salida, exist_ok=True)
    destino = os.path.join(carpeta_salida, f'{nombre} vertical.drb')
    numeros = tuple(k for k in range(1, len(combos) + 1) if k not in QUITAR)
    guardadas = {k: g.COMBINACIONES.get(k) for k in numeros}
    try:
        for k in numeros:
            g.COMBINACIONES[k] = combos[k - 1]
        C.construir(contenedor, destino, f'{nombre} vertical', 'superior', numeros, y_por_comb='centro', nombres_nuevos=True,
                    guia=True)       # guia=True: sin ajuste automático de ancho ni mayúsculas del macro (el tamaño lo manda el zoom de cada palabra)
    finally:
        for k, v in guardadas.items():
            if v is None:
                g.COMBINACIONES.pop(k, None)
            else:
                g.COMBINACIONES[k] = v
    try:
        import packs_drt
        pos = packs_drt.posiciones_de_drb(destino)
        with open(os.path.join(carpeta_salida, f'{nombre} vertical.posiciones.json'), 'w', encoding='utf-8') as fh:
            json.dump({'origen': os.path.basename(destino), 'clips': {k: list(v) for k, v in pos.items()}}, fh, indent=1)
    except Exception:
        pass
    with open(os.path.join(carpeta_salida, 'pack.json'), 'w', encoding='utf-8') as fh:
        json.dump({'version': 2, 'nombre': nombre, 'formatos': {'v': {'drb': os.path.basename(destino)}}, 'guion': 'referencia'}, fh, ensure_ascii=False, indent=2)
    return destino


if __name__ == '__main__':
    salida = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.expanduser('~'), 'DaVinciSubtitles', 'plantillas', 'Referencia')
    print(construir(salida))
