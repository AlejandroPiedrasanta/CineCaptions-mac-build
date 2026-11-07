# CineCaptions · By Cinema Productions
# 2_recursos/generador_packs/pack_viral.py — arma el pack «VIRAL»: los elementos del estilo de subtítulos virales (línea fina, negrita, shatter, select, drag).
"""
Uso:  python pack_viral.py [--lab] [<carpeta de salida>]      (por defecto 2_recursos/plantillas_incluidas/VIRAL)
      python pack_viral.py --tema5                            (v5.76: el pack «Tema5»: solo «v tipo», en vertical; ver construir_tema5)

Genera «VIRAL vertical.drb» y «VIRAL horizontal.drb» (un clip por elemento, ver viral_elementos.py; el horizontal lleva las mismas comps con las medidas de un cuadro 1920×1080) y su pack.json
con «guion»: «viral»: la marca con la que la app sabe que este pack se coloca con viral_planificador.py. Comparte con Kinetic el camino de Resolve (place_kinetic_track) y el generador de clips (kinetic_pack.py).
--lab  añade los clips de laboratorio «v lab …» (viral_lab.py) para probar qué admite Fusion; NO deben ir en la versión que se entrega.
Al cambiar cualquier comp hay que subir plantillas.REVISION_BIN['VIRAL']: sin eso Resolve reutiliza el bin viejo del proyecto.
"""
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(AQUI, '..', '..', '1_codigo'))
import kinetic_pack


def construir(carpeta_salida=None, nombre='VIRAL', contenedor=None, lab=False, formatos=('v', 'h'), solo=None):
    """Arma los .drb de cada formato («VIRAL vertical.drb», «VIRAL horizontal.drb») y el pack.json. Devuelve (ruta del vertical, [clips]).
    `solo`: los clips que lleva (None = todos)."""
    base = os.path.abspath(os.path.join(AQUI, '..', 'plantillas_incluidas'))
    carpeta_salida = carpeta_salida or os.path.join(base, nombre)
    contenedor = contenedor or os.path.join(base, 'Referencia', 'Referencia vertical.drb')
    os.makedirs(carpeta_salida, exist_ok=True)
    nombres_formato = {'v': 'vertical', 'h': 'horizontal'}
    json_formatos, destinos, clips = {}, {}, []
    import viral_elementos
    try:
        for f in formatos:
            comps = dict(viral_elementos.todos(f))
            if lab:
                import viral_lab
                comps.update(viral_lab.todos())
            if solo:
                comps = {k: v for k, v in comps.items() if k in solo}
            destino = os.path.join(carpeta_salida, f'{nombre} {nombres_formato[f]}.drb')
            kinetic_pack.construir_clips(contenedor, destino, f'{nombre} {nombres_formato[f]}', comps, clip_base='principal')
            json_formatos[f] = {'drb': os.path.basename(destino)}
            destinos[f] = destino
            clips = list(comps)
    finally:
        viral_elementos.configurar('v')          # deja las medidas de kinetic_comps como estaban (vertical): otro generador en el mismo proceso no debe heredar el cuadro horizontal
    with open(os.path.join(carpeta_salida, 'pack.json'), 'w', encoding='utf-8') as fh:
        json.dump({'version': 2, 'nombre': nombre, 'formatos': json_formatos, 'guion': 'viral'}, fh, ensure_ascii=False, indent=2)
    return destinos.get('v') or next(iter(destinos.values())), clips


def construir_tema5(carpeta_salida=None):
    """v5.76 (el usuario: «aplícalo en Tema 5, elimina el estilo del Tema 5»): el pack «Tema5» es ahora un pack de ELEMENTOS como el VIRAL
    («guion»: «viral», el mismo colocador) con UN clip, «v tipo» (viral_elementos.comp_tipo; lo planifica tipo_planificador.py), solo en vertical
    como antes. Sus escenas de la PRO no cambian (van por el nombre del tema). El Tema 6 sigue con pack_tema5.py."""
    return construir(carpeta_salida, nombre='Tema5', formatos=('v',), solo=('v tipo',))


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if '--tema5' in sys.argv:
        d, clips = construir_tema5(args[0] if args else None)
        print(d, len(clips), 'clips:', ', '.join(clips))
        sys.exit(0)
    d, clips = construir(args[0] if args else None, lab='--lab' in sys.argv)
    print(d, len(clips), 'clips:', ', '.join(clips))
