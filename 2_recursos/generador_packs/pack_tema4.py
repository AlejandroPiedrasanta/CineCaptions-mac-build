# CineCaptions · By Cinema Productions
# 2_recursos/generador_packs/pack_tema4.py — arma el pack «Tema4» (Tema 4): captions blancos de una sola tipografía que se arman palabra a palabra en un recuadro.
"""
El pack «Tema4» replica TEMA 4.mp4 del usuario (v5.4.33):

    todo el texto es Inter Bold BLANCO con el espaciado de letras apretado y el brillo suave de los macros Luxe; solo cambia el TAMAÑO de cada palabra:
        principal = la palabra clave, la más grande          (Luxe Shine, brillo corto)
        abajo     = las palabras normales                    (Luxe Slide)
        arriba    = las conectoras pequeñas (es, lo, que, de…) (Luxe Slide)
    Los tres roles llevan la MISMA tipografía y el MISMO «Size» base (grande): el planificador (tema4_planificador.py) pone el zoom de cada palabra, así que el texto siempre se
    rasteriza al tamaño mayor y se REDUCE (nunca se amplía).

Todos los clips van CENTRADOS en el cuadro (Tilt 0): la posición de cada palabra la pone el script (Pan/Tilt por palabra, estilo «guion»).
Uso:  python pack_tema4.py [<carpeta de salida>]
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
FUENTE = ('Inter 24pt', 'Bold')
TAM_BASE = 0.14                  # «Size» base (≈ 90 px de letra a 1080 de ancho): el mayor tamaño que pide el planificador (la clave ≈ 84 px); el resto se reduce con el zoom
ESPACIADO = 0.97                 # letras apretadas, como la referencia
BRILLO = (26.0, 0.95)            # halo blanco suave (tamaño, intensidad): el de fábrica (17,3 · 0,48) se queda corto frente a la referencia
ANIM = (0.10, 0.08)              # entrada y salida del macro en segundos (la referencia entra en 3 fotogramas)


def _rol(tam=TAM_BASE, color=BLANCO):
    return dict(f1=FUENTE, f2=FUENTE, tam=tam, esp=ESPACIADO, mayus=False, color=color, retardo=0)


def combinaciones():
    c = {'nombre': 'Blanco', 'context': _rol(), 'main': _rol(), 'complement': _rol(), 'entrada': 'sube', 'luxe': True, 'mayus_real': True, 'anim': ANIM,
         'barrido': {'modo': 'brillo', 'inicio': 0.04, 'largo': 0.30}, 'brillo': BRILLO}
    return [c]


def construir(carpeta_salida, nombre='Tema4', contenedor=None):
    """Genera <carpeta_salida>/<nombre> vertical.drb (+ .variantes.json, pack.json y .posiciones.json). Devuelve la ruta del .drb."""
    import plantillas
    incluidas = plantillas.carpeta_incluida()
    contenedor = contenedor or str(incluidas / 'Viral Superior' / 'Viral Superior vertical.drb')
    combos = combinaciones()
    os.makedirs(carpeta_salida, exist_ok=True)
    destino = os.path.join(carpeta_salida, f'{nombre} vertical.drb')
    guardadas = {k: g.COMBINACIONES.get(k) for k in range(1, len(combos) + 1)}
    try:
        for k, c in enumerate(combos, 1):
            g.COMBINACIONES[k] = c
        C.construir(contenedor, destino, f'{nombre} vertical', 'superior', tuple(range(1, len(combos) + 1)), y_por_comb='centro', nombres_nuevos=True,
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
        json.dump({'version': 2, 'nombre': nombre, 'formatos': {'v': {'drb': os.path.basename(destino)}}, 'guion': 'tema4'}, fh, ensure_ascii=False, indent=2)
    return destino


if __name__ == '__main__':
    salida = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.expanduser('~'), 'DaVinciSubtitles', 'plantillas', 'Tema4')
    print(construir(salida))
