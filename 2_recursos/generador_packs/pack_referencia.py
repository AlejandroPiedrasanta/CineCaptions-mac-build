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
# v5.50 (pedido: «entrada y salida muy rápidas»): MEDIDO contra PRUEBAS (3) a 30 fps, la referencia entra en 8-9 fotogramas (la grande) y 4-6 (las
# pequeñas) y sale en 4-5; con 0,28/0,22 y el tope del 30 % salían la mitad. 0,60/0,45 con tope 50 % / 35 % del clip (la suma nunca llega al clip).
ANIM = (0.60, 0.45, 0.50, 0.35)
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
        c['principal_drb'] = {'drb': amro[0], 'clip': 'principal' if amro[1] == 1 else f'principal {amro[1]}', 'cambios': amro[2] if len(amro) > 2 else ()}
    return c


# v5.50 (pedido: «la barra debe quedar al ras de la palabra»): la barra del Underline de Amro es el Text+ «Line» (su recuadro, encogido y bajado
# con Offset8, en fracción del alto). MEDIDO en Resolve: quedaba 12 px (a zoom 1) bajo la tinta de las letras; con -0,032 ya las tapaba 7 px.
# v5.50 (pedido: «1-9-13 agregas halftone»; luego «están feos: debe ser todo, sutil y difuminado»): puntos azul oscuro (#16357A) por TODA la letra,
# de bordes suaves y poca opacidad (40 % en la base que se desvanece a 12 % arriba)
TRAMA_IMPACTO = {'color': (0.086, 0.208, 0.478), 'celda': 9, 'radio': 2.4, 'suave': 1.6, 'opacidad': (0.4, 0.12)}
# A lo ancho, la barra es la caja del MISMO texto en «Line»: su fuente, peso y espaciado siguen a los de la palabra (Text1) por expresión (la fuente de
# «Crea tu estilo» la cambia el script solo en Text1: con Arial Black la barra salía más ancha) y ExtendHorizontal8 recorta el margen de la caja
# (MEDIDO: -0,1 recorta 22 px por lado a zoom 1; con las fuentes enlazadas sobraban 13 px -> -0,16).
BARRA_AL_RAS = (('Offset8 = Input { Value = { 0, -0.042 }, }', 'Offset8 = Input { Value = { 0, -0.036 }, }'),
                ('ExtendVertical8 = Input { Value = -0.342, }', 'ExtendVertical8 = Input { Value = -0.342, }, ExtendHorizontal8 = Input { Value = -0.16, }'),
                ('StyledText = Input { Value = "standard 1", Expression = "Text1.StyledText", }, Font = Input { Value = "Inter", }, Style = Input { Value = "Black", }, ',
                 'StyledText = Input { Value = "standard 1", Expression = "Text1.StyledText", }, Font = Input { Value = "Inter", Expression = "Text1.Font", }, '
                 'Style = Input { Value = "Black", Expression = "Text1.Style", }, '),
                ('CharacterSpacing = Input { Value = 0.958, }, TransformRotation = Input { Value = 1, }, TransformPivot',
                 'CharacterSpacing = Input { Value = 0.958, Expression = "Text1.CharacterSpacing", }, TransformRotation = Input { Value = 1, }, TransformPivot'))

# v5.53 (pedido: «Amro Fire corta las palabras largas»): el Fire de Amro dibuja las letras en un cuadro de 1080 y las encoge DESPUÉS (Transform1
# al 0,66): una palabra más ancha que el cuadro antes de encoger («PRINCIPAL») salía sin los bordes («Principa»). Ahora las letras nacen ya al 0,66
# y el Transform se queda en 1. El tamaño de cada letra lo da la curva del Follower («Follower1Tamaño»), no el Size del Text+ ni el «tam» de la
# variante (medido: cambiarlos no cambia nada); lo que dependía de esa escala (rejilla, ruido, difuminado, sombra) se ajusta igual para que se vea lo mismo.
FUEGO_SIN_RECORTE = (('[0] = { 0, RH = { 0, 0.576 }, Flags = { Linear = true } }', '[0] = { 0, RH = { 0, 0.3802 }, Flags = { Linear = true } }'),
                     ('[10] = { 0.409, LH = { 6.66667, 0.409 } }', '[10] = { 0.2699, LH = { 6.66667, 0.2699 } }'),
                     ('Size = Input { Value = 0.66, }', 'Size = Input { Value = 1, }'),
                     ('SoftnessX1 = Input { Value = 16.85, }', 'SoftnessX1 = Input { Value = 11.12, }'),
                     ('SoftnessY1 = Input { Value = 17.17, }', 'SoftnessY1 = Input { Value = 11.33, }'),
                     ('vernum = Input { Value = 31, }', 'vernum = Input { Value = 47, }'),
                     ('hornum = Input { Value = 70, }', 'hornum = Input { Value = 106, }'),
                     ('XScale = Input { Value = 5.04, }', 'XScale = Input { Value = 7.64, }'),
                     ('ShadowDistance = Input { Value = 0.0898, }', 'ShadowDistance = Input { Value = 0.0593, }'),
                     ('shadowBlur = Input { Value = 0.882, }', 'shadowBlur = Input { Value = 0.582, }'))


def combinaciones(ruta_amro):
    base = [
        _combo('Impacto cian', _rol(('Poppins', 'ExtraBold'), 0.257, CIAN, mayus=True, esp=ESPACIADO), barrido=BARRIDO_BRILLO),
        _combo('Editorial rosa', _rol(('DM Serif Text', 'Italic'), 0.28, ROSA, esp=ESPACIADO), entrada='abre', barrido=BARRIDO_BRILLO),
        _combo('Amro Highlight naranja', _rol(('Inter', 'Black'), 0.17, (1.0, 0.55, 0.15), mayus=True), amro=(ruta_amro, 1)),
        _combo('Moderno blanco', _rol(('Poppins', 'Bold'), 0.18, BLANCO, esp=ESPACIADO), entrada='sube', barrido=BARRIDO_BRILLO),
        _combo('Editorial azul', _rol(('DM Serif Text', 'Italic'), 0.28, AZUL, esp=ESPACIADO), entrada='abre', barrido=BARRIDO_BRILLO),
        _combo('Amro Fire', _rol(('Inter', 'Black'), 0.17, (1.0, 0.30, 0.15), mayus=True), amro=(ruta_amro, 5, FUEGO_SIN_RECORTE)),
        _combo('Amro Strike rojo', _rol(('Inter', 'Black'), 0.17, (1.0, 0.28, 0.28), mayus=True), amro=(ruta_amro, 6)),
        _combo('Amro Underline lima', _rol(('Inter', 'Black'), 0.17, (0.62, 1.0, 0.30), mayus=True), amro=(ruta_amro, 3, BARRA_AL_RAS)),
    ]
    base[0]['trama'] = TRAMA_IMPACTO        # v5.50: el Impacto cian (1) y sus barridos (9, 13: se copian de él aquí abajo) llevan halftone
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
