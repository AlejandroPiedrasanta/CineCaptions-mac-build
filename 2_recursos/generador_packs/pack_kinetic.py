# CineCaptions · By Cinema Productions
# 2_recursos/generador_packs/pack_kinetic.py — arma el pack «Kinetic»: los elementos del estilo de títulos de gancho (héroe, líneas, serif, pincel, cintas, anillos, subrayados).
"""
Uso:  python pack_kinetic.py [<carpeta de salida>]      (por defecto 2_recursos/plantillas_incluidas/Kinetic)

Genera «Kinetic vertical.drb» (un clip por elemento, ver kinetic_elementos.py) y su pack.json con «guion»: «kinetic», que es la marca con la que la app sabe
que este pack se coloca con el planificador de kinetic_planificador.py (y NO con el de 3 líneas ni con el «guion»). Solo vertical.
Al cambiar cualquier comp hay que subir plantillas.REVISION_BIN['Kinetic']: sin eso Resolve reutiliza el bin viejo del proyecto.
"""
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(AQUI, '..', '..', '1_codigo'))
import kinetic_elementos
import kinetic_pack


def construir(carpeta_salida=None, nombre='Kinetic', contenedor=None):
    base = os.path.abspath(os.path.join(AQUI, '..', 'plantillas_incluidas'))
    carpeta_salida = carpeta_salida or os.path.join(base, nombre)
    contenedor = contenedor or os.path.join(base, 'Referencia', 'Referencia vertical.drb')
    os.makedirs(carpeta_salida, exist_ok=True)
    destino = os.path.join(carpeta_salida, f'{nombre} vertical.drb')
    comps = kinetic_elementos.todos()
    kinetic_pack.construir_clips(contenedor, destino, f'{nombre} vertical', comps, clip_base='principal')
    with open(os.path.join(carpeta_salida, 'pack.json'), 'w', encoding='utf-8') as fh:
        json.dump({'version': 2, 'nombre': nombre, 'formatos': {'v': {'drb': os.path.basename(destino)}}, 'guion': 'kinetic'}, fh, ensure_ascii=False, indent=2)
    return destino, list(comps)


if __name__ == '__main__':
    d, clips = construir(sys.argv[1] if len(sys.argv) > 1 else None)
    print(d, len(clips), 'clips')
