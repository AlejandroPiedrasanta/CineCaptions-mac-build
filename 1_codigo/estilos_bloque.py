# CineCaptions · By Cinema Productions
# 1_codigo/estilos_bloque.py — qué estilo (variante del pack) lleva CADA bloque: lo decide la app y lo enseña Creativo, ya no el azar de Resolve.
"""
Un pack trae hasta 3 estilos (principal / principal 2 / principal 3, con sus arriba y abajo). Hasta la v5.7 el reparto entre bloques se sorteaba DENTRO de
Resolve (la «rueda» de CineCaptions.py y la de CineCaptions_Subtitulos.lua, con semillas distintas): la app no podía decirte qué estilo llevaría un bloque y el mismo
video salía distinto en Studio y en Free. Ahora:

  * asignar() decide el estilo de cada bloque con apoyo (arriba/abajo): la rueda de siempre (sin repetir dos seguidos, misma semilla), o el estilo FIJO que
    elegiste en «Estilos del pack», o el que cambiaste a mano en Creativo para ese bloque (palabras[primera palabra del bloque]['estilo'] = n);
  * escribe b['estilo'] = n (el NÚMERO de la variante del pack) en cada bloque: los dos scripts de Resolve lo respetan; sin él (manifiestos viejos) usan su rueda;
  * Creativo llama a la MISMA función con las marcas de ese momento, así que «Así se verá este bloque» enseña exactamente el estilo que saldrá.
"""
import random

SEMILLA = 20260806


def orden_de_variantes(cantidad_bloques, cantidad_sets, semilla=SEMILLA):
    """Qué variante le toca a cada bloque, sin repetir nunca dos seguidas (gemela de la del script de Resolve)."""
    if cantidad_sets <= 1:
        return [0] * cantidad_bloques
    rnd = random.Random(semilla)
    orden = []
    ultimo = None
    while len(orden) < cantidad_bloques:
        vuelta = list(range(cantidad_sets))
        rnd.shuffle(vuelta)
        if vuelta[0] == ultimo:
            vuelta[0], vuelta[1] = vuelta[1], vuelta[0]
        orden.extend(vuelta)
        ultimo = vuelta[-1]
    return orden[:cantidad_bloques]


def usa_set(bloque):
    """True si el bloque lleva arriba/principal/abajo (y no es una palabra suelta): la misma regla que _usa_set de los scripts."""
    return any(l.get('role') != 'base' for l in (bloque or {}).get('lines', []))


def indice_de_palabras(bloques):
    """Para cada palabra del texto, el número de su bloque (así lo calcula también Creativo para el hover)."""
    indice = []
    for k, b in enumerate(bloques):
        for linea in b.get('lines') or []:
            indice.extend([k] * len(str(linea.get('text') or '').split()))
    return indice


def primera_palabra_de(bloques, k):
    """El índice de la primera palabra del bloque k (donde se guarda su estilo manual), o None."""
    for i, kk in enumerate(indice_de_palabras(bloques)):
        if kk == k:
            return i
    return None


def asignar(bloques, palabras, numeros, fijo=0):
    """Pone b['estilo'] = n en cada bloque con apoyo. numeros = los números de variante del pack (p. ej. [1, 2, 3]); fijo = la variante fija (0 = alternar).
    Devuelve {k: n}. Sin números no toca nada."""
    numeros = [int(n) for n in numeros or []]
    if not numeros:
        return {}
    candidatos = [k for k, b in enumerate(bloques) if usa_set(b)]
    if fijo and int(fijo) in numeros:
        reparto = [int(fijo)] * len(candidatos)
    else:
        reparto = [numeros[v] for v in orden_de_variantes(len(candidatos), len(numeros))]
    primeras = {}
    for i, kk in enumerate(indice_de_palabras(bloques)):
        primeras.setdefault(kk, i)
    asignados = {}
    for pos, k in enumerate(candidatos):
        n = reparto[pos]
        i = primeras.get(k)
        if i is not None and i < len(palabras or []):
            manual = (palabras[i] or {}).get('estilo')
            if isinstance(manual, int) and manual in numeros:
                n = manual
                bloques[k]['estilo_manual'] = True
        bloques[k]['estilo'] = n
        asignados[k] = n
    for k, b in enumerate(bloques):
        if k not in asignados:
            b.pop('estilo', None)
            b.pop('estilo_manual', None)
    return asignados
