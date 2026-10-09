# CineCaptions · By Cinema Productions
# 1_codigo/probar_barrido.py — prueba en el banco zz_BANCO (Resolve) del BARRIDO DE LUZ de las palabras grandes del pack «Referencia»: ¿llega hasta el final de la palabra, en cuánto tiempo?
"""
Uso:   python probar_barrido.py [--estilos 1,9,13] [--palabras GO,IMPACT,REMARKABLE] [--duraciones 0.35,0.6,1.2] [--nombre barrido] [--temporal]

Pone una palabra grande por cada combinación (estilo × duración que se ve) en el timeline temporal zz_BANCO, con el MISMO colocador de Resolve que usa GO (place_guion_track: incluye el
ajuste del barrido a lo que dura cada palabra), renderiza y saca una hoja con 6 cuadros de cada una (entrada + 0,05 s, +0,15, +0,25, +0,35, +0,5 s y el último antes de salir). Siempre limpia
(vuelve al timeline que tenía el usuario).
Estilos: 1 cian · 2 rosa · 4 blanco · 5 azul (barrido original) · 9-12 Screen · 13-16 Sólido (ver generador_packs/pack_referencia.py).
"""
import os
import sys
from pathlib import Path

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import banco_pruebas  # noqa: E402

CARPETA = banco_pruebas.CARPETA


def _arg(argv, nombre, defecto=None):
    return argv[argv.index(nombre) + 1] if nombre in argv else defecto


def main(argv):
    import guion_captions as G
    estilos = [int(x) for x in _arg(argv, '--estilos', '1,9,13,2,10,14,4,11,15,5,12,16').split(',')]
    palabras = _arg(argv, '--palabras', 'IMPACT,GO,REMARKABLE').split(',')
    duraciones = [float(x) for x in _arg(argv, '--duraciones', '0.35,0.6,1.2').split(',')]
    nombre = _arg(argv, '--nombre', 'barrido')
    bloques, tiempos = [], []
    t = 0.6
    k = 0
    for n in estilos:
        for d in duraciones:
            texto = palabras[k % len(palabras)]
            k += 1
            bloques.append({'t0': t, 't1': t + d, 'estilo': n, 'lineas': [('M', [(texto, t, n)], 0.5, 0.5, 0.6)], 'caja': (0.42, 0.58)})
            for dt in (0.05, 0.15, 0.25, 0.35, 0.5):
                tiempos.append(round(t + dt, 2))
            tiempos.append(round(t + d - 0.08, 2))
            t += d + 0.55
    cues = G.construir_cues(bloques, 'Referencia', 1080)
    fin = t + 0.8
    print(f'{len(cues)} palabras · {fin:.1f} s', flush=True)
    ruta = None
    try:
        r = banco_pruebas.preparar(color=(24, 24, 28), frames=int(fin * 30) + 30, fps=30, renovar=('Referencia',))
        print('banco:', r, flush=True)
        ok, msg = banco_pruebas.colocar_guion(cues, 'Referencia', 'en', 'barrido_prueba')
        print('colocar:', 'OK' if ok else 'FALLO', str(msg)[-1800:], flush=True)
        if ok:
            ruta = banco_pruebas.renderizar(nombre, tope_s=420)
            print('render:', ruta, flush=True)
    finally:
        print('limpiar:', banco_pruebas.limpiar(), flush=True)
    if ruta:
        print('hoja:', banco_pruebas.hoja(ruta, tiempos, str(CARPETA / f'hoja_{nombre}.png'), ancho=170, recorte=(0.40, 0.60), columnas=6, fps=30, aspecto=1920 / 1080), flush=True)


if __name__ == '__main__':
    argv = [a for a in sys.argv[1:] if a != '--temporal']
    if '--temporal' in sys.argv:                  # en un proyecto TEMPORAL y vacío de Resolve (no ensucia el del usuario); ver proyecto_pruebas.py
        import proyecto_pruebas
        print('proyecto temporal:', proyecto_pruebas.entrar(), flush=True)
        try:
            main(argv)
        finally:
            print('de vuelta:', proyecto_pruebas.salir(), flush=True)
    else:
        main(argv)
