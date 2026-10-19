# CineCaptions · By Cinema Productions
# 1_codigo/mezcla_planificador.py — «Crea tu estilo» con los estilos de los TRES temas: Tema 1 (títulos de gancho), Tema 2 (palabra a palabra) y Tema 3 (viral), mezclados por frases.
"""
mezcla_planificador.py  (v5.4.30)
---------------------------------
Un estilo propio («pack de mezcla») es una LISTA DE LOOKS elegidos entre los tres temas:

    Tema 1 · Kinetic    una receta (héroe lima, blanco con anillo, magenta, amarillo, serif, blanco y cian)             -> motor «kinetic»
    Tema 2 · Referencia un estilo de palabra grande (Impacto cian, Editorial rosa, Amro Highlight…)                     -> motor «guion»
    Tema 3 · VIRAL      pila fina + negrita, o un efecto (shatter, select, drag)                                        -> motor «viral»

Cada tema ya sabe armar sus bloques con su propio planificador; aquí NO se toca ninguno. Se parte lo hablado en TRAMOS (una o varias frases seguidas), cada tramo recibe un look
(rotando por la lista) y el planificador de ese tema arma SOLO las palabras de su tramo. Luego se juntan los bloques, se cuida que dos bloques no se pisen en pantalla y salen
dos listas: los bloques de formato «kinetic» (Tema 1 y Tema 3, que comparten colocador de Resolve) y los de formato «guion» (Tema 2).

    planificar(palabras, looks, idioma, ancho_tl, alto_tl, ...) -> {'kinetic': [cues], 'guion': [cues], 'orden': [(motor, cue)], 'tramos': [...], 'packs': {'kinetic', 'viral', 'guion'}}

Es determinista (mismo audio y mismos looks → mismo resultado) y no habla con Resolve.
"""
from pathlib import Path

import guion_captions as GC
import guion_planificador as GP
import kinetic_captions as KC
import kinetic_planificador as KP
import viral_captions as VC
import viral_planificador as VP

MIN_PALABRAS_TRAMO = 5              # un tramo junta frases hasta llegar a esto (o a MIN_SEGUNDOS_TRAMO)
MIN_SEGUNDOS_TRAMO = 2.6
GAP = 0.03                          # lo mínimo que separa el final de un bloque del principio del siguiente (s)

# ----------------------------------------------------------------------------------------------------------------------------- el catálogo de looks
NOMBRES_T1 = {'lima': 'Círculo lima', 'blanco-rojo': 'Pegatina roja', 'magenta': 'Magenta subrayado', 'amarillo': 'A mano y pegatina', 'serif': 'Lazo magenta', 'blanco-cian': 'A mano subrayada'}   # v5.5.13: tema neón
NOMBRES_T3 = {'pila': 'Pila y negrita', 'v shatter': 'Shatter (cristal)', 'v select': 'Select (caja)', 'v drag': 'Drag (mano)'}


def catalogo():
    """Todos los looks disponibles: [{'id', 'tema', 'motor', 'nombre', ...}] en el orden en que se enseñan (Tema 1, Tema 2, Tema 3)."""
    salida = []
    for k, r in enumerate(KP.RECETAS):
        salida.append({'id': f"t1:{r['nombre']}", 'tema': 1, 'motor': 'kinetic', 'receta': k, 'nombre': NOMBRES_T1.get(r['nombre'], r['nombre'].capitalize())})
    try:
        variantes = GC.datos_variantes('Referencia', 'v')
    except Exception:
        variantes = {}
    for n in (1, 2, 3, 4, 5, 6, 7, 8):
        nombre = (variantes.get(n) or {}).get('nombre') or f'Estilo {n}'
        salida.append({'id': f't2:{n}', 'tema': 2, 'motor': 'guion', 'estilo': n, 'nombre': nombre})
    for clave, nombre in NOMBRES_T3.items():
        salida.append({'id': f"t3:{clave.replace('v ', '')}", 'tema': 3, 'motor': 'viral', 'efecto': None if clave == 'pila' else clave, 'nombre': nombre})
    return salida


def look_de(id_):
    return next((l for l in catalogo() if l['id'] == id_), None)


# ----------------------------------------------------------------------------------------------------------------------------- tramos
def tramos(palabras):
    """Parte lo hablado en tramos de frases seguidas: [(i0, i1)] con índices de la lista ORIGINAL de palabras (i1 incluido)."""
    pal = GP._preparar(palabras)
    if not pal:
        return []
    grupos = []
    for frase in GP.frases(pal):
        orig = sorted(o for k in frase for o in pal[k]['orig'])
        grupos.append((orig[0], orig[-1], pal[frase[0]]['t'], pal[frase[-1]]['fin'], len(frase)))
    salida, i0, t0, n = [], None, None, 0
    for a, b, t_a, t_b, c in grupos:
        if i0 is None:
            i0, t0, n = a, t_a, 0
        n += c
        fin_i, fin_t = b, t_b
        if n >= MIN_PALABRAS_TRAMO or fin_t - t0 >= MIN_SEGUNDOS_TRAMO:
            salida.append([i0, fin_i])
            i0 = None
    if i0 is not None:
        if salida and n < 3:
            salida[-1][1] = fin_i                   # un cabo suelto de 1-2 palabras se une al tramo anterior
        else:
            salida.append([i0, fin_i])
    return [(a, b) for a, b in salida]


# ----------------------------------------------------------------------------------------------------------------------------- piezas que hacen que cada planificador use SOLO el look elegido
class _Fijo:
    """Un dict «de mentira» que devuelve siempre `valor` (los planificadores piden `recetas.get(i, i)`, `efectos.get(i)`, `estilos.get(n)`)."""

    def __init__(self, valor):
        self.valor = valor

    def get(self, _i, _defecto=None):
        return self.valor


class _Ciclo:
    """Lo mismo pero alterna entre varios valores (los barridos de luz de un estilo Luxe: original → Screen → Sólido), siguiendo un contador compartido entre tramos."""

    def __init__(self, valores, contador):
        self.valores = tuple(valores)
        self.contador = contador

    def get(self, _i, _defecto=None):
        v = self.valores[self.contador[0] % len(self.valores)]
        self.contador[0] += 1
        return v


def _fin_de(palabras, i1, siguiente_t, fin_video):
    """El fin que se le da al último bloque del tramo: el principio del tramo siguiente (para no pisarlo) o, en el último tramo, el fin del video."""
    if siguiente_t is not None:
        return float(siguiente_t)
    return fin_video


def _cues_kinetic(sub, look, idioma, ancho_tl, alto_tl, ancla, mains, fin):
    res = KP.planificar(sub, idioma=idioma, ancho_tl=ancho_tl, alto_tl=alto_tl, ancla=ancla, mains=mains, recetas=_Fijo(look['receta']), fin_video=fin)
    return res['cues'], res['plan']


def _cues_viral(sub, look, idioma, ancho_tl, alto_tl, ancla, mains, fin):
    anterior = VP.ROTACION
    try:
        if look.get('efecto'):
            VP.ROTACION = (look['efecto'],)                           # SOLO ese efecto rota (cada 2 bloques, como el tema)
            res = VP.planificar(sub, idioma=idioma, ancho_tl=ancho_tl, alto_tl=alto_tl, ancla=ancla, mains=mains, fin_video=fin)
            if res['cues'] and not any(str(r.get('k', '')).startswith(look['efecto']) for c in res['cues'] for r in (c.get('runs') or [])):
                # un tramo de pocos bloques (el tema saca un efecto cada 2) se quedaría sin el look elegido: se pide el efecto en el último bloque
                res = VP.planificar(sub, idioma=idioma, ancho_tl=ancho_tl, alto_tl=alto_tl, ancla=ancla, mains=mains, efectos={len(res['plan']) - 1: look['efecto']}, fin_video=fin)
        else:
            res = VP.planificar(sub, idioma=idioma, ancho_tl=ancho_tl, alto_tl=alto_tl, ancla=ancla, mains=mains, efectos=_Fijo(False), fin_video=fin)
    finally:
        VP.ROTACION = anterior
    return res['cues'], res['plan']


def _cues_guion(sub, look, idioma, ancho_tl, ancla, mains, fin, contador_barrido):
    n = look['estilo']
    try:
        con_variantes = set(GC.datos_variantes('Referencia', 'v').keys())
    except Exception:
        con_variantes = set()
    barridos = GP.BARRIDOS.get(n)
    if barridos and all(v in con_variantes for v in barridos):
        estilos = _Ciclo(barridos, contador_barrido)               # el estilo base con su barrido de luz alternando (como en el tema)
    else:
        estilos = _Fijo(n)
    bloques, plan = GP.planificar(sub, idioma, 'Referencia', ancho_tl, ancla=ancla, mains=mains, estilos=estilos, fin_video=fin, variar_barrido=False)
    return GC.construir_cues(bloques, 'Referencia', ancho_tl), plan


# ----------------------------------------------------------------------------------------------------------------------------- el planificador
def planificar(palabras, looks, idioma='es', ancho_tl=1080, alto_tl=1920, ancla_kinetic='bajo', ancla_viral='bajo', ancla_guion='medio', mains=None, fin_video=None):
    """palabras [{'word','start','end'}] y `looks` (lista de ids del catálogo, en el orden en que rotan) → ver el docstring del módulo."""
    elegidos = [l for l in (look_de(i) for i in (looks or [])) if l]
    if not elegidos or not palabras:
        return {'kinetic': [], 'guion': [], 'orden': [], 'tramos': [], 'packs': set()}
    partes = tramos(palabras)
    contador_barrido = [0]
    veces_color = {}
    salida = []                                           # [(motor, cue, tramo)]
    resumen = []
    for n, (i0, i1) in enumerate(partes):
        look = elegidos[n % len(elegidos)]
        sub = palabras[i0:i1 + 1]
        t_sig = palabras[partes[n + 1][0]].get('start') if n + 1 < len(partes) else None
        fin = _fin_de(palabras, i1, t_sig, fin_video)
        mains_sub = None
        if mains:
            mains_sub = [m for m in mains if not isinstance(m, int)] or None   # (los forzados por índice se cuentan sobre la lista completa: aquí solo valen las palabras)
        if look['motor'] == 'kinetic':
            cues, plan = _cues_kinetic(sub, look, idioma, ancho_tl, alto_tl, ancla_kinetic, mains_sub, fin)
            motor = 'kinetic'
        elif look['motor'] == 'viral':
            cues, plan = _cues_viral(sub, look, idioma, ancho_tl, alto_tl, ancla_viral, mains_sub, fin)
            motor = 'viral'
            for c in cues:                                # los colores de los efectos siguen rotando ENTRE tramos (el planificador solo cuenta dentro del suyo)
                bases = {r.get('k', '').split(' ')[0] + ' ' + (r.get('k', '').split(' ')[1] if ' ' in r.get('k', '') else '') for r in (c.get('runs') or [])}
                for base in [b for b in bases if b in VC.COLORES]:
                    k = veces_color.get(base, 0)
                    veces_color[base] = k + 1
                    nuevo = VC.nombre_variante(base, k)
                    for r in c.get('runs') or []:
                        if str(r.get('k', '')).startswith(base):
                            r['k'] = nuevo
        else:
            cues, plan = _cues_guion(sub, look, idioma, ancho_tl, ancla_guion, mains_sub, fin, contador_barrido)
            motor = 'guion'
        for c in cues:
            salida.append((motor, c))
        resumen.append({'tramo': n, 'look': look['id'], 'motor': motor, 'palabras': i1 - i0 + 1, 'bloques': len(cues)})
    salida.sort(key=lambda mc: float(mc[1].get('start', 0)))
    # que dos bloques no se pisen en pantalla (aunque sean de temas distintos): el que llega primero se acorta si el siguiente entra antes de que termine
    for k in range(len(salida) - 1):
        _m, c = salida[k]
        _m2, sig = salida[k + 1]
        limite = float(sig['start']) - GAP
        if float(c['end']) > limite:
            c['end'] = round(max(float(c['start']) + 0.25, limite), 3)
            for r in c.get('runs') or []:
                if isinstance(r.get('fin'), (int, float)) and r['fin'] > c['end']:
                    r['fin'] = c['end']
    packs = set()
    for m, _c in salida:
        packs.add({'kinetic': 'kinetic', 'viral': 'viral', 'guion': 'guion'}[m])
    return {'kinetic': [c for m, c in salida if m in ('kinetic', 'viral')], 'guion': [c for m, c in salida if m == 'guion'],
            'orden': salida, 'tramos': resumen, 'packs': packs}


# ----------------------------------------------------------------------------------------------------------------------------- el pack de mezcla en el disco
MAX_LOOKS = 8                                       # los looks que rotan en un pack (más no se nota: un tramo dura 3-5 s)


def crear_pack(nombre, looks, carpeta_packs=None):
    """Guarda «Mi estilo» como un pack del usuario: solo `pack.json` ({"guion": "mezcla", "looks": [...]}) y la foto de muestra de su tarjeta (vista_mezcla.jpg). No lleva clips propios:
    al generar, cada tema pone los suyos (los .drb de fábrica de Kinetic, Referencia y VIRAL). Devuelve (nombre, carpeta)."""
    import plantillas
    import archivos_seguros
    ids = []
    for i in looks or []:
        if look_de(i) is not None and i not in ids:
            ids.append(i)
    ids = ids[:MAX_LOOKS]
    if not ids:
        raise ValueError('elige al menos un estilo')
    nombre = (nombre or 'Mi estilo')[:40].strip() or 'Mi estilo'
    base = Path(carpeta_packs) if carpeta_packs else plantillas.carpeta_de_packs()
    carpeta = base / plantillas.nombre_seguro(nombre)           # la misma carpeta que plantillas.buscar_pack(nombre) mira
    carpeta.mkdir(parents=True, exist_ok=True)
    archivos_seguros.escribir_json(carpeta / 'pack.json', {'version': 2, 'nombre': nombre, 'guion': 'mezcla', 'looks': ids, 'formatos': {'v': {'mezcla': True}}}, indent=2)
    try:
        import mezcla_vista
        mezcla_vista.poster(ids, foto=0, ancho=540).save(carpeta / 'vista_mezcla.jpg', quality=88)
    except Exception:
        pass
    try:
        plantillas.invalidar_packs()
    except Exception:
        pass
    return nombre, carpeta


def resumen(res):
    """El plan en una tabla legible (para depurar)."""
    filas = ['  tramo look            motor    palabras bloques']
    for t in res.get('tramos', []):
        filas.append(f"  {t['tramo']:4d} {t['look']:<15s} {t['motor']:<8s} {t['palabras']:8d} {t['bloques']:7d}")
    return '\n'.join(filas)
