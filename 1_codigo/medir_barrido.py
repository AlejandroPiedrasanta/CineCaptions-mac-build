# CineCaptions · By Cinema Productions
# 1_codigo/medir_barrido.py — mide, sobre un render de probar_barrido.py, si el barrido de luz recorre TODA la palabra y cuánto dura.
"""
Uso:   python medir_barrido.py <render.mov> [--estilos 9,13,...] [--palabras IMPACT,GO,REMARKABLE] [--duraciones 0.4,0.7]   (los mismos valores con los que se hizo el render)

Por cada palabra: cuadros a 30 fps desde que entra hasta que sale; el perfil de luminosidad por columnas de cada cuadro menos el perfil «sin barrido» (la mediana de los cuadros) da dónde
está la banda de luz en cada instante. Informa en qué fracción del ancho de la letra empieza y acaba (0 % = borde izquierdo, 100 % = borde derecho), el primer y el último cuadro con barrido
y cuánto dura. Un barrido correcto empieza cerca del 0-15 % y acaba pasado el 85 %.
"""
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)


UMBRAL = 2.5                                      # diferencia de luminosidad (0-255) mínima para decir «aquí hay barrido»


def _arg(argv, nombre, defecto=None):
    return argv[argv.index(nombre) + 1] if nombre in argv else defecto


def main(argv):
    import numpy as np
    import banco_pruebas as B
    ruta = argv[0]
    estilos = [int(x) for x in _arg(argv, '--estilos', '1,9,13,2,10,14,4,11,15,5,12,16').split(',')]
    palabras = _arg(argv, '--palabras', 'IMPACT,GO,REMARKABLE').split(',')
    duraciones = [float(x) for x in _arg(argv, '--duraciones', '0.35,0.6,1.2').split(',')]
    fps = 30.0
    t, k, citas = 0.6, 0, []
    for n in estilos:
        for d in duraciones:
            citas.append((n, d, palabras[k % len(palabras)], t))
            k += 1
            t += d + 0.55
    todos = {}
    for _n, d, _p, t0 in citas:
        for f in range(int(t0 * fps), int((t0 + d + 0.1) * fps) + 1):
            todos[f] = None
    cuadros = B.cuadros(ruta, sorted(todos), ancho=540, alto=960)
    print(f'{"estilo":>6} {"palabra":<11} {"dur":>5}  {"barrido desde":>13} {"hasta":>7} {"dura":>6}  {"recorre":>14}  veredicto')
    for n, d, palabra, t0 in citas:
        f0, f1 = int(t0 * fps), int((t0 + d + 0.1) * fps)
        perfiles = []
        for f in range(f0, f1 + 1):
            im = cuadros.get(f)
            if im is None:
                continue
            gris = im[int(960 * 0.40):int(960 * 0.60)].astype('float32').mean(axis=2)
            perfiles.append((f, gris.mean(axis=0)))
        if len(perfiles) < 4:
            print(f'{n:>6} {palabra:<11} {d:>5.2f}  (sin cuadros)')
            continue
        matriz = np.array([p for _f, p in perfiles])
        base = np.median(matriz, axis=0)
        activo = np.nonzero(base > base.max() * 0.25)[0]
        if len(activo) < 5:
            print(f'{n:>6} {palabra:<11} {d:>5.2f}  (no hay texto)')
            continue
        izq, der = int(activo[0]), int(activo[-1])
        ancho = max(1, der - izq)
        pos, quedan = [], []
        for (f, p) in perfiles:
            dif = np.clip(p - base, 0, None)
            dif[:max(0, izq - 12)] = 0
            dif[der + 12:] = 0
            if dif.max() > UMBRAL:
                cx = float((dif * np.arange(len(dif))).sum() / dif.sum())
                pos.append(((cx - izq) / ancho, f))
        if len(pos) < 2:
            print(f'{n:>6} {palabra:<11} {d:>5.2f}  (no se ve barrido)')
            continue
        xs = [x for x, _f in pos]
        fs = [f for _x, f in pos]
        dura = (max(fs) - min(fs) + 1) / fps
        ok = min(xs) <= 0.25 and max(xs) >= 0.75
        print(f'{n:>6} {palabra:<11} {d:>5.2f}  {(min(fs) / fps - t0):>12.2f}s {(max(fs) / fps - t0):>6.2f}s {dura:>5.2f}s  {min(xs) * 100:>5.0f}% a {max(xs) * 100:>4.0f}%  {"completo" if ok else "INCOMPLETO"}')


if __name__ == '__main__':
    main(sys.argv[1:])
