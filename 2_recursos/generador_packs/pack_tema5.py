# CineCaptions · By Cinema Productions
# 2_recursos/generador_packs/pack_tema5.py — arma los packs «Tema5» y «Tema6»: los captions Text+ EDITABLES con el diseño de sus captions de Remotion.
"""
v5.5.8 — los Temas 5 y 6 ponen por defecto captions Text+ editables (edicion_pro.OPCIONES_POR_DEFECTO['pro_captions_editables']) en lugar de los de
Remotion (remotion/src/Subtitulo.tsx). Estos packs les dan su diseño (el armado es el del Tema 4: pack_tema4.construir):

    Tema5:  principal = la FRASE CLAVE en DM Serif Text Italic, en el color de acento del video (edicion_pro_tema5.ACENTOS: una variante por color:
            1 azul · 2 ámbar · 3 lima · 4 lila; tema4_planificador elige la del video con acento_de_video)
            abajo / arriba = lo que se dice, Inter 18pt Medium BLANCA y pequeña
    Tema6:  todo en Instrument Serif (alta y fina, recta): la clave grande en lima #DDF25E (variante 1) o blanca (variante 2) según
            edicion_pro_tema6.color_clave; lo demás pequeño y blanco

Tipografías, tamaños base y espaciado salen de tema4_planificador.DISENOS (el planificador mide con ellas: una sola fuente de verdad). El tamaño
base de cada rol es el de su letra a zoom ≈ 1; el planificador pone el zoom de cada palabra. Principal = Luxe Shine, abajo/arriba = Luxe Slide.
Uso:  python pack_tema5.py [Tema5|Tema6] [<carpeta de salida>] [--retocar <.drb ya armado>]     (sin carpeta: 2_recursos/plantillas_incluidas/<pack>)
      --retocar (v5.54): solo el acabado sobre ese .drb, sin generar los macros otra vez (los de fábrica son los Luxe de antes de la v1.09)
      Al cambiar un pack, subir plantillas.REVISION_BIN['<pack>'].
"""
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(AQUI, '..', '..', '1_codigo'))
import pack_tema4

BRILLO = (10.0, 0.30)            # el halo de los macros, suave (Remotion no lleva brillo: solo una sombra fina)
# v5.54 «B · Premium» (la propuesta que eligió el usuario): la clave con el degradado de su color y un brillo de su color más visible; lo pequeño al
# 90 % de blanco; todas con la sombra ancha (luxe_macro._premium)
PREMIUM = {'brillo_principal': (18.0, 0.62)}
PEQUENA = (0.9, 0.9, 0.9)
ANIM = (0.16, 0.10)              # entrada y salida del macro (Remotion: la sans entra en 0,28 s, la clave en 0,42 s, desenfocada → nítida)
NOMBRES = {'azul': 'Azul', 'ambar': 'Ámbar', 'lima': 'Lima', 'lila': 'Lila', 'blanco': 'Blanco'}


def _rgb(hexa):
    h = hexa.lstrip('#')
    return tuple(round(int(h[k:k + 2], 16) / 255.0, 4) for k in (0, 2, 4))


def _colores(pack):
    if pack == 'Tema5':
        import edicion_pro_tema5 as T5
        return T5.ACENTOS
    import edicion_pro_tema6 as T6
    return {'lima': T6.LIMA, 'blanco': T6.BLANCO}


def combinaciones(pack):
    import tema4_planificador as T
    D = T.DISENOS[pack]
    colores = _colores(pack)
    sans = dict(f1=D['sans'], f2=D['sans'], tam=D['tam_sans'], esp=D['esp_sans'], mayus=False, color=PEQUENA, retardo=0)
    out = []
    for nombre in D['variantes']:
        clave = dict(f1=D['serif'], f2=D['serif'], tam=D['tam_serif'], esp=D['esp_serif'], mayus=False, color=_rgb(colores[nombre]), retardo=0)
        out.append({'nombre': NOMBRES[nombre], 'context': dict(sans), 'main': clave, 'complement': dict(sans), 'entrada': 'sube', 'luxe': True,
                    'mayus_real': True, 'anim': ANIM, 'barrido': {'modo': 'brillo', 'inicio': 0.04, 'largo': 0.30}, 'brillo': BRILLO, 'premium': PREMIUM})
    return out


def construir(pack, carpeta_salida=None, retocar=None):
    """retocar: ver pack_tema4.construir (v5.54: el acabado «B · Premium» sobre el .drb de fábrica)."""
    import plantillas
    carpeta_salida = carpeta_salida or str(plantillas.carpeta_incluida() / pack)
    return pack_tema4.construir(carpeta_salida, nombre=pack, combos=combinaciones(pack), guion=pack.lower(), retocar=retocar)


if __name__ == '__main__':
    args = sys.argv[1:]
    retocar = args.pop(args.index('--retocar') + 1) if '--retocar' in args else None
    args = [a for a in args if a != '--retocar']
    print(construir(args[0] if args else 'Tema5', args[1] if len(args) > 1 else None, retocar=retocar))
