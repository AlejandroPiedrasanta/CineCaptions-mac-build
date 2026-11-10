# CineCaptions · By Cinema Productions
# 1_codigo/mezcla_planificador.py — «Crea tu estilo»: los Temas 1 a 6 ENTEROS mezclados por frases (y los looks sueltos de los packs de antes) y el estilo del usuario en el disco (pack.json).
"""
mezcla_planificador.py  (v5.56; v5.4.30 la mezcla de looks de los Temas 1-3)
-----------------------------------------------------------------------------
Un estilo propio es la LISTA de temas que el usuario tocó, en ese orden. Desde la v5.56 son TEMAS ENTEROS ('t1'…'t6', TEMAS_ENTEROS):

    t1 · Tema 1 (pack «Kinetic»)      motor «kinetic»  títulos de gancho con la composición del kit; sus seis recetas rotan por todo el video
    t2 · Tema 2 (pack «Referencia»)   motor «guion»    palabra a palabra, con su rotación de estilos y sus barridos de luz
    t3 · Tema 3 (pack «VIRAL»)        motor «viral»    pila fina + negrita y un efecto (select, shatter, drag) cada dos bloques, en su orden
    t4 · Tema 4 (pack «Tema4»)        motor «guion»    el recuadro limpio; la palabra clave en una de cada tres frases
    t5 · Tema 5 (pack «Tema5»)        motor «viral»    (v5.76) la palabra clave grande y la serif cursiva que la muerde, palabra a palabra
                                                       (tipo_planificador, clip «v tipo» del pack Tema5); sin la «Edición total»
    t6 · Tema 6 (pack «Tema6»)        motor «guion»    sus captions Text+ (lima o blanco según de qué hable el video); sin la «Edición total»

Los ids de los packs de antes siguen valiendo (catalogo(): 't1:<receta>', 't2:<n>', 't3:pila|shatter|select|drag'): un look FIJO de un tema.

Lo hablado se parte en TRAMOS (tramos(): frases seguidas hasta 5 palabras o 2,6 s, y desde ahí hasta un FIN DE ORACIÓN siempre que se pueda;
una frase que pasa del tope, habla seguida sin signos ni pausas, se parte donde mejor se respira: _partir_larga) y
cada tramo lleva el tema que le toca en el orden del usuario (tramo n -> temas[n % len(temas)]). Los contadores de cada tema siguen de un tramo
al siguiente, como si el tema fuera solo (si no, todos los tramos de un tema empezarían igual):
  · Tema 1: la receta. KP pide recetas.get(i) una vez por bloque: un _Ciclo con un contador compartido.
  · Tema 3: «un efecto cada `cada` bloques» cuenta también los bloques del Tema 3 de los tramos anteriores, y la rotación de efectos sigue donde
    se quedó (_EfectosTema3 los pide bloque a bloque: NO se toca el global VP.ROTACION, así dos hilos pueden planificar a la vez).
  · Tema 5 (v5.76, «v tipo»): tramo a tramo, cada tramo con sus bloques (tipo_planificador); si un bloque espera, TP.reajustar corrige sus tiempos.
  · Temas 2, 4 y 6: UNA sola llamada a su planificador con las palabras de TODOS sus tramos, cada tramo cerrado con 'fin_frase' (entre dos
    tramos del mismo tema siempre hay otro tramo, así que nunca se juntan): su rotación de estilos, sus barridos, el ritmo de la palabra clave
    y el color del Tema 6 siguen solos. Los Temas 1 y 3 van tramo a tramo porque lo que deciden (el aro que se dibuja, el efecto que cabe)
    depende de cuándo acaba el bloque, y eso solo se sabe tramo a tramo. Con marcas «Principal» de Creativo, los Temas 2, 4, 5 y 6 también van
    tramo a tramo (las marcas mandan donde están; en los tramos sin marcas, lo automático).
  Con UN solo tema entero el video se planifica de una vez: sale igual que el tema solo (la mezcla no toca ni un tiempo).
Entre bloques de temas distintos queda GAP y ninguno se queda en un «relámpago» (si haría falta, el del tema siguiente espera un poco para
entrar, como hace el Tema 2 entre sus bloques); entre bloques del mismo tema, los huecos del tema (_sin_pisarse). Los bloques de un tramo van
siempre antes que los del siguiente: uno que su tema hizo esperar hasta el tramo de otro tema entra antes, cuando se dice (_a_su_hora).

    planificar(palabras, looks, idioma, ancho_tl, alto_tl, ..., mains=None, fin_video=None, video=None) ->
        {'kinetic': [cues de T1 y T3], 'guion': [cues de T2, T4, T5 y T6], 'orden': [(motor, cue)] por tiempo (motor 'kinetic' | 'viral' | 'guion'),
         'tramos': [{'tramo', 'look', 'pack', 'tema', 'motor', 'palabras', 'bloques', 'i0', 'i1', 'inicio', 'fin', 'detalle'}],
         'packs': {nombres de pack}, 'packs_kinetic': [...], 'packs_guion': [...] (en el orden del usuario), 'motores': {...}, 'contadores': {...}}
    Cada cue lleva c['pack'] = el pack BASE de su tema ('Kinetic', 'VIRAL', 'Referencia', 'Tema4', 'Tema5' o 'Tema6') y NINGUNA clave de emoji
    (sin la Edición PRO no hay emojis: si van, los pone GO después con su regla).

    crear_estilo(nombre, temas, ajustes) -> el pack.json del estilo del usuario (2-6 temas: una mezcla; 1 tema: un pack DERIVADO {'base': pack}).
    crear_pack(nombre, looks) -> el pack de mezcla de antes (sigue funcionando).

Es determinista (mismo audio y mismos temas → mismo resultado) y no habla con Resolve.
"""
import re
from pathlib import Path

import guion_captions as GC
import guion_planificador as GP
import kinetic_captions as KC  # noqa: F401  (lo importaban los de antes)
import kinetic_planificador as KP
import viral_captions as VC
import viral_planificador as VP

MIN_PALABRAS_TRAMO = 5              # un tramo junta frases hasta llegar a esto (o a MIN_SEGUNDOS_TRAMO)…
MIN_SEGUNDOS_TRAMO = 2.6
MAX_PALABRAS_TRAMO = 16             # …y sigue hasta un FIN DE ORACIÓN; si no llega ninguno, corta en el fin de frase que toque al pasar de esto
MAX_SEGUNDOS_TRAMO = 7.0
PAUSA_ORACION = 1.0                 # una pausa así cierra la oración aunque no haya punto (como el Tema 4)
GAP = 0.03                          # lo mínimo que separa el final de un bloque del principio del de OTRO tema (s); dentro de un tema, el hueco del tema
MIN_BORDE = 0.33                    # un recorte en el cambio de tema no deja un bloque en menos de esto (sería un «relámpago»)…
ESPERA_MAX = 0.35                   # …el bloque del tema siguiente espera para entrar como mucho esto (lo mismo que el Tema 2 entre sus bloques: GP._respiro)
MIN_VIEJO = 0.25                    # (los looks sueltos de los packs de antes se recortan como siempre: GAP con el siguiente, sin bajar de esto)

# ----------------------------------------------------------------------------------------------------------------------------- los temas enteros (v5.56)
# NO van en catalogo(): esa la usan la galería vieja y hacer_vistas_mezcla. look_de() mira las dos.
TEMAS_ENTEROS = (
    {'id': 't1', 'tema': 1, 'motor': 'kinetic', 'pack': 'Kinetic', 'entero': True, 'nombre': 'Estilo 1'},
    {'id': 't2', 'tema': 2, 'motor': 'guion', 'pack': 'Referencia', 'entero': True, 'nombre': 'Estilo 2'},
    {'id': 't3', 'tema': 3, 'motor': 'viral', 'pack': 'VIRAL', 'entero': True, 'nombre': 'Estilo 3'},
    {'id': 't4', 'tema': 4, 'motor': 'guion', 'pack': 'Tema4', 'entero': True, 'nombre': 'Estilo 4'},
    {'id': 't5', 'tema': 5, 'motor': 'viral', 'pack': 'Tema5', 'entero': True, 'nombre': 'Estilo 5'},       # v5.76: «v tipo» (antes «guion»)
    {'id': 't6', 'tema': 6, 'motor': 'guion', 'pack': 'Tema6', 'entero': True, 'nombre': 'Estilo 6'},
    {'id': 't7', 'tema': 7, 'motor': 'viral', 'pack': 'Tema7', 'entero': True, 'nombre': 'Estilo 7'},       # v5.78: «v rojo» (linea_planificador, perfil ROJO)
    {'id': 't8', 'tema': 8, 'motor': 'viral', 'pack': 'Tema8', 'entero': True, 'nombre': 'Estilo 8'},       # v5.80: «v ambar» (ambar_planificador)
    {'id': 't9', 'tema': 9, 'motor': 'viral', 'pack': 'Tema9', 'entero': True, 'nombre': 'Estilo 9'},       # v5.80: «v edi» (editorial_planificador)
)
# v5.80: los temas enteros que tienen su PROPIO planificador de elementos (mismo contrato que viral_planificador.planificar, sin ancla)
PLANIFICADOR_PROPIO = {'t5': 'tipo_planificador', 't8': 'ambar_planificador', 't9': 'editorial_planificador'}
MAX_TEMAS = len(TEMAS_ENTEROS)       # un estilo lleva de 1 a 6 temas, sin repetir
PACK_DE_MOTOR = {'kinetic': 'Kinetic', 'viral': 'VIRAL', 'guion': 'Referencia'}          # el pack de los looks sueltos de antes
MOTOR_DE_PACK = {l['pack']: l['motor'] for l in TEMAS_ENTEROS}

# ----------------------------------------------------------------------------------------------------------------------------- el catálogo de looks (packs de antes)
NOMBRES_T1 = {'lima': 'Círculo lima', 'blanco-rojo': 'Pegatina roja', 'magenta': 'Magenta subrayado', 'amarillo': 'A mano y pegatina', 'serif': 'Lazo magenta', 'blanco-cian': 'A mano subrayada'}   # v5.5.13: tema neón
NOMBRES_T3 = {'pila': 'Pila y negrita', 'v shatter': 'Shatter (cristal)', 'v select': 'Select (caja)', 'v drag': 'Drag (mano)',
              'v corte': 'Corte', 'v shine': 'Giro 3D', 'v resalta': 'Resaltado', 'v linea': 'Línea con caja'}   # v5.75: EJEMPLO 2 (se parte), EJEMPLO3 (letras con volumen que giran), selección del iPhone


def catalogo():
    """Los looks sueltos de los packs de antes: [{'id', 'tema', 'motor', 'nombre', ...}] en el orden en que se enseñaban (Tema 1, Tema 2, Tema 3)."""
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


# ----------------------------------------------------------------------------------------------------------------------------- «Crea tu estilo» v5.75
# La página se divide en TEXTO BASE (las palabras normales de arriba y abajo: se elige una o ninguna) y TEXTOS PRINCIPALES (la palabra con efecto:
# varias, se turnan por frases). Solo lo que se ve distinto en MOVIMIENTO: lo que solo cambia de color sale una vez (el color va en «Letra y colores»).
#   · una base = la LETRA de arriba y abajo de su tema (ajustes['fuente_secundaria']) puesta en TODOS los principales; cada principal guarda su tamaño y su sitio
#   · un principal = un look que la mezcla ya sabe turnar (un look suelto 't2:6' o un tema entero 't4'); su previa: 2_recursos/guia_estilo/crea/<id>.mp4
BASES_CREA = (
    {'id': 'b_t1_amano', 'tema': 1, 'n': 1, 'fuente': 'Yellowtail|Regular'},          # «k script yt» (a mano)
    {'id': 'b_t1_serif', 'tema': 1, 'n': 2, 'fuente': 'DM Serif Text|Italic'},        # «k serif»
    {'id': 'b_t2', 'tema': 2, 'fuente': 'Poppins|Light'},                             # guion_captions.FINA
    {'id': 'b_t3', 'tema': 3, 'fuente': 'Inter 18pt|Medium'},                         # «v fina» (la del Tema 5 es la misma: no sale)
    {'id': 'b_t4', 'tema': 4, 'fuente': 'Inter 24pt|Bold'},                           # tema4_planificador.FUENTE
    {'id': 'b_t6', 'tema': 6, 'fuente': 'Instrument Serif|Regular'},                  # Tema6 vertical.variantes.json
)
PRINCIPALES_CREA = (
    {'id': 'p_t1_circulo', 'tema': 1, 'look': 't1:lima', 'efecto': 'Círculo'},         # recetas 1 y 5 (idénticas)
    {'id': 'p_t1_subrayado', 'tema': 1, 'look': 't1:magenta', 'efecto': 'Subrayado'},
    {'id': 'p_t2_impacto', 'tema': 2, 'look': 't2:1', 'efecto': 'Barrido'},          # Luxe Shine (el 4 es el mismo en otro color)
    {'id': 'p_t2_editorial', 'tema': 2, 'look': 't2:2', 'efecto': 'Barrido'},        # Luxe Shine (el 5 es el mismo en otro color)
    {'id': 'p_t2_highlight', 'tema': 2, 'look': 't2:3', 'efecto': 'Fondo'},
    {'id': 'p_t2_fire', 'tema': 2, 'look': 't2:6', 'efecto': 'Fuego'},
    {'id': 'p_t2_strike', 'tema': 2, 'look': 't2:7', 'efecto': 'Tachado'},
    {'id': 'p_t2_underline', 'tema': 2, 'look': 't2:8', 'efecto': 'Subrayado'},
    {'id': 'p_t3_select', 'tema': 3, 'look': 't3:select', 'efecto': 'Caja'},
    {'id': 'p_t3_shatter', 'tema': 3, 'look': 't3:shatter', 'efecto': 'Cristal'},
    {'id': 'p_t3_drag', 'tema': 3, 'look': 't3:drag', 'efecto': 'Arrastre'},
    {'id': 'p_t3_corte', 'tema': 3, 'look': 't3:corte', 'efecto': 'Corte'},           # v5.75: rosa con volumen que se parte en 6 trozos
    {'id': 'p_t3_shine', 'tema': 3, 'look': 't3:shine', 'efecto': 'Giro 3D'},         # v5.75: naranja con volumen, letras que giran una tras otra
    {'id': 'p_t3_resalta', 'tema': 3, 'look': 't3:resalta', 'efecto': 'Resaltado'},   # v5.75: la selección azul del iPhone con su asa
    {'id': 'p_t3_linea', 'tema': 3, 'look': 't3:linea', 'efecto': 'Línea'},            # v5.75: el Tema 3 nuevo (una línea, caja que salta); caja azul
    {'id': 'p_t4', 'tema': 4, 'look': 't4', 'efecto': 'Brillo'},
    {'id': 'p_t5', 'tema': 5, 'look': 't5', 'efecto': 'Tipografía'},                # v5.76: el Tema 5 nuevo (grande + serif que la muerde)
    {'id': 'p_t6', 'tema': 6, 'look': 't6', 'efecto': 'Brillo'},
    {'id': 'p_t7', 'tema': 7, 'look': 't7', 'efecto': 'Palabra roja'},           # v5.78: el Estilo 7 (la que suena en rojo; el color = el «color principal»)
    {'id': 'p_t8', 'tema': 8, 'look': 't8', 'efecto': 'Ámbar'},                  # v5.80: el Estilo 8 (la clave en negrita ámbar)
    {'id': 'p_t9', 'tema': 9, 'look': 't9', 'efecto': 'Serif cursiva'},          # v5.80: el Estilo 9 (la clave grande en serif cursiva)
)


def base_crea(id_):
    """La base de «Crea tu estilo» con ese id (copia) o None."""
    return next((dict(b) for b in BASES_CREA if b['id'] == str(id_ or '')), None)


def principal_crea(id_):
    """El principal de «Crea tu estilo» con ese id o con ese look ('t2:6', 't4'); copia o None."""
    id_ = str(id_ or '')
    return next((dict(p) for p in PRINCIPALES_CREA if id_ in (p['id'], p['look'])), None)


def nombre_crea(item):
    """Lo que ve el usuario: «Tema 1 · 2» (base de un tema con dos) o «Tema 2 · Fuego» (principal). Solo «Tema N», sin apodos."""
    if not item:
        return ''
    if 'efecto' in item:
        return tr('Estilo {n} · {e}', n=item['tema'], e=tr(item['efecto']))
    return tr('Estilo {n} · {k}', n=item['tema'], k=item['n']) if item.get('n') else tr('Estilo {n}', n=item['tema'])


def temas_enteros():
    """Los seis temas enteros (copias: se pueden tocar sin miedo)."""
    return [dict(l) for l in TEMAS_ENTEROS]


def es_tema_entero(id_):
    return any(l['id'] == str(id_ or '') for l in TEMAS_ENTEROS)


def look_de(id_):
    """El look con ese id: un tema entero ('t1'…'t6') o un look suelto de antes ('t1:lima', 't2:3', 't3:shatter'…); None si no existe."""
    id_ = str(id_ or '').strip()
    for l in TEMAS_ENTEROS:
        if l['id'] == id_:
            return dict(l)
    if ':' not in id_:
        return None
    return next((l for l in catalogo() if l['id'] == id_), None)


def pack_de_look(look):
    """El nombre del pack BASE de un look: el de su tema entero o, en los looks sueltos de antes, el de su motor (Kinetic, Referencia, VIRAL)."""
    return (look or {}).get('pack') or PACK_DE_MOTOR.get((look or {}).get('motor'))


class _Packs(set):
    """Los NOMBRES de los packs que usa la mezcla ({'Kinetic', 'VIRAL', 'Referencia', 'Tema4'…}). El GO de antes preguntaba por el MOTOR
    ('kinetic' in packs, 'viral' in packs): esas preguntas siguen contestando bien mientras GO se pone al día (al iterar solo salen nombres)."""

    def __init__(self, nombres=(), motores=()):
        super().__init__(nombres)
        self.motores = frozenset(motores)

    def __contains__(self, x):
        return set.__contains__(self, x) or x in self.motores


# ----------------------------------------------------------------------------------------------------------------------------- tramos
def _cierra_oracion(pal, k, con_signos):
    """¿La palabra k (preparada por GP._preparar) cierra una oración? Signo fuerte, fin de frase marcado por la app, la última, una pausa de
    PAUSA_ORACION o, si el texto no trae ningún signo (la IA los quitó), una pausa de oración del Tema 2 sin coma escrita."""
    w = pal[k]
    if k + 1 >= len(pal):
        return True
    signo = w.get('signo') or ''
    if (signo and signo in GP._FUERTE) or w.get('fin_frase'):
        return True
    hueco = float(pal[k + 1]['t']) - float(w['fin'])
    if hueco >= PAUSA_ORACION:
        return True
    return (not con_signos) and not (signo and signo in GP._COMA) and hueco >= float(GP.AFINADO.get('pausa_oracion', 0.3))


def _larga(pal, ks):
    return len(ks) > MAX_PALABRAS_TRAMO or pal[ks[-1]]['fin'] - pal[ks[0]]['t'] > MAX_SEGUNDOS_TRAMO


def _partir_larga(pal, frase):
    """Una frase que no cabe en un tramo (más de MAX_PALABRAS_TRAMO palabras o MAX_SEGUNDOS_TRAMO s: habla seguida, sin signos ni pausas de 0,2 s, que
    GP.frases deja entera) en trozos que sí caben, de al menos MIN_PALABRAS_TRAMO palabras (o MIN_SEGUNDOS_TRAMO s) y sin dejar al final un cabo de
    1-2 palabras. Se corta donde mejor se respira, como GP._corte: nunca tras «de», «la», «que»… si se puede; luego la pausa más larga (una coma
    escrita o una conjunción detrás ayudan) y, a igualdad, el trozo más cerca de 10 palabras. -> [[k, ...], ...] ([frase] si ya cabe)."""
    ideal = (MIN_PALABRAS_TRAMO + MAX_PALABRAS_TRAMO) / 2.0
    trozos, resto = [], list(frase)
    while len(resto) > 1 and _larga(pal, resto):
        validos, cortos = [], []
        for j in range(len(resto) - 1):                   # cortar tras resto[j]
            pieza = resto[:j + 1]
            if _larga(pal, pieza):
                break
            if len(resto) - j - 1 < 3:
                break
            llega = len(pieza) >= MIN_PALABRAS_TRAMO or pal[pieza[-1]]['fin'] - pal[pieza[0]]['t'] >= MIN_SEGUNDOS_TRAMO
            (validos if llega else cortos).append(j)
        opciones = validos or cortos or [0]

        def nota(j):
            k, k2 = resto[j], resto[j + 1]
            pausa = float(pal[k2]['t']) - float(pal[k]['fin'])
            if pal[k]['signo'] and pal[k]['signo'] in GP._COMA:
                pausa += 0.15
            if pal[k2]['plano'] in GP._CONJ:
                pausa += 0.05
            return (not GP._debil(pal, k), int(round(pausa / 0.05)), -abs(j + 1 - ideal))
        j = max(opciones, key=nota)
        trozos.append(resto[:j + 1])
        resto = resto[j + 1:]
    if resto:
        trozos.append(resto)
    return trozos


def tramos(palabras):
    """Parte lo hablado en tramos de frases seguidas: [(i0, i1)] con índices de la lista ORIGINAL de palabras (i1 incluido).
    Un tramo junta frases (GP.frases) hasta MIN_PALABRAS_TRAMO o MIN_SEGUNDOS_TRAMO y desde ahí corta en el primer FIN DE ORACIÓN (v5.56; antes
    cortaba en cualquier fin de frase, a veces a mitad de oración); si en MAX_PALABRAS_TRAMO / MAX_SEGUNDOS_TRAMO no llega ninguno, corta en el fin
    de frase que toque. Una frase que sola ya pasa del tope (habla seguida sin signos ni pausas: GP.frases no la corta) se parte antes donde mejor
    se respira (_partir_larga): si no, todo el video sería un solo tramo y del estilo solo se vería el primer tema. Un cabo suelto de 1-2 palabras
    al final se une al tramo anterior."""
    pal = GP._preparar(palabras)
    if not pal:
        return []
    con_signos = any((w['signo'] and w['signo'] in GP._FUERTE) or w.get('fin_frase') for w in pal)
    grupos = []
    for frase in GP.frases(pal):
        trozos = _partir_larga(pal, frase)
        for n_t, trozo in enumerate(trozos):
            orig = sorted(o for k in trozo for o in pal[k]['orig'])
            forzado = n_t + 1 < len(trozos)                  # el corte de un trozo de una frase larga vale como tope
            grupos.append((orig[0], orig[-1], pal[trozo[0]]['t'], pal[trozo[-1]]['fin'], len(trozo), _cierra_oracion(pal, trozo[-1], con_signos), forzado))
    salida, i0, t0, n, fin_i = [], None, None, 0, None
    for a, b, t_a, t_b, c, cierra, forzado in grupos:
        if i0 is None:
            i0, t0, n = a, t_a, 0
        n += c
        fin_i, fin_t = b, t_b
        llega = n >= MIN_PALABRAS_TRAMO or fin_t - t0 >= MIN_SEGUNDOS_TRAMO
        tope = n >= MAX_PALABRAS_TRAMO or fin_t - t0 >= MAX_SEGUNDOS_TRAMO or forzado
        if llega and (cierra or tope):
            salida.append([i0, fin_i])
            i0 = None
    if i0 is not None:
        if salida and n < 3:
            salida[-1][1] = fin_i                   # un cabo suelto de 1-2 palabras se une al tramo anterior
        else:
            salida.append([i0, fin_i])
    return [(a, b) for a, b in salida]


# ----------------------------------------------------------------------------------------------------------------------------- piezas que se pasan a los planificadores
class _Fijo:
    """Un dict «de mentira» que devuelve siempre `valor` (los planificadores piden `recetas.get(i, i)`, `efectos.get(i)`, `estilos.get(n)`)."""

    def __init__(self, valor):
        self.valor = valor

    def get(self, _i, _defecto=None):
        return self.valor


class _Ciclo:
    """Lo mismo pero alterna entre varios valores siguiendo un contador compartido entre tramos (las recetas del Tema 1; los barridos de luz de
    un estilo Luxe suelto: original → Screen → Sólido)."""

    def __init__(self, valores, contador):
        self.valores = tuple(valores)
        self.contador = contador

    def get(self, _i, _defecto=None):
        v = self.valores[self.contador[0] % len(self.valores)]
        self.contador[0] += 1
        return v


class _Efectos:
    """`efectos=` de viral_planificador hecho con una función: índice de bloque -> clip pedido, False (sin efecto) o None (lo decide el tema)."""

    def __init__(self, fn):
        self.fn = fn

    def get(self, i, _defecto=None):
        return self.fn(i)


def _base_efecto(tipo):
    """'v shatter rosa' -> 'v shatter'; 'pila' / None -> lo mismo."""
    return VC.base_de(str(tipo or ''))


class _EfectosTema3:
    """`efectos=` del Tema 3 entero dentro de la mezcla: un efecto cada `cada` bloques CONTANDO los bloques del Tema 3 de los tramos anteriores, y
    en el orden de VP.ROTACION desde donde se quedó (estado {'bloques', 'rot'}). Se lee VP.ROTACION, nunca se cambia (antes se ponía el global y
    otro hilo podía planificar a la vez con el valor cambiado). Un efecto pedido que no cabe baja a «shatter», el más corto, como en el tema."""

    def __init__(self, estado):
        self.estado = estado
        self.siguiente = int(estado.get('rot', 0))

    def get(self, i, _defecto=None):
        cada = max(1, int(VP.AFINADO.get('cada', 2) or 2))
        if (int(self.estado.get('bloques', 0)) + int(i)) % cada != cada - 1:
            return False
        rotacion = tuple(VP.ROTACION) or ('v shatter',)
        efecto = rotacion[self.siguiente % len(rotacion)]
        self.siguiente += 1
        return efecto


def _cerrar_tema3(estado, plan):
    """Tras planificar un tramo del Tema 3: suma sus bloques y deja la rotación detrás del último efecto que salió de verdad."""
    rotacion = tuple(VP.ROTACION)
    salieron = [b for b in (_base_efecto(p.get('tipo')) for p in plan) if b in rotacion]
    estado['bloques'] = int(estado.get('bloques', 0)) + len(plan)
    if salieron:
        estado['rot'] = rotacion.index(salieron[-1]) + 1


def _rotar_colores(cues, veces):
    """Los colores de los efectos rotan ENTRE tramos (el planificador solo cuenta dentro del suyo): la vez k de cada efecto, su variante k."""
    for c in cues:
        bases = []
        for r in c.get('runs') or []:
            b = _base_efecto(r.get('k'))
            if b in VC.COLORES and b not in bases:
                bases.append(b)
        for base in bases:
            k = veces.get(base, 0)
            veces[base] = k + 1
            nuevo = VC.nombre_variante(base, k)
            for r in c.get('runs') or []:
                if str(r.get('k', '')).startswith(base):
                    r['k'] = nuevo


def _mains_tramo(mains, palabras, i0, i1, desplazar=0):
    """Las marcas «Principal» (Creativo) que caen en el tramo i0..i1: los índices, RELATIVOS al tramo (+ desplazar); las palabras (texto), solo si
    se dicen en él (si no, el planificador se quedaría sin palabras grandes en ese tramo)."""
    if not mains:
        return []
    salida, planos = [], None
    for m in mains:
        if m is None or isinstance(m, bool):
            continue
        if isinstance(m, int):
            if i0 <= m <= i1:
                salida.append(int(m) - i0 + desplazar)
            continue
        texto = str(m).strip()
        if not texto:
            continue
        if planos is None:
            planos = {GP._plano(str(w.get('word', ''))) for w in palabras[i0:i1 + 1]}
        if GP._plano(texto) in planos and texto not in salida:
            salida.append(texto)
    return salida


# ----------------------------------------------------------------------------------------------------------------------------- los looks sueltos de antes (un look FIJO por tramo)
def _cues_kinetic(sub, look, idioma, ancho_tl, alto_tl, ancla, mains, fin):
    res = KP.planificar(sub, idioma=idioma, ancho_tl=ancho_tl, alto_tl=alto_tl, ancla=ancla, mains=mains, recetas=_Fijo(look['receta']), fin_video=fin)
    return res['cues'], res['plan']


def _cues_viral(sub, look, idioma, ancho_tl, alto_tl, ancla, mains, fin):
    """Un look suelto del Tema 3: SOLO su efecto, cada `cada` bloques como el tema (o en las palabras marcadas). v5.56: se pide bloque a bloque
    (_Efectos) en vez de cambiar el global VP.ROTACION; un efecto que no cabe se queda en pila, como antes, y si el tramo se queda sin el look
    elegido se pide en su último bloque."""
    kw = dict(idioma=idioma, ancho_tl=ancho_tl, alto_tl=alto_tl, ancla=ancla, mains=mains, fin_video=fin)
    efecto = look.get('efecto')
    if not efecto:
        res = VP.planificar(sub, efectos=_Fijo(False), **kw)
        return res['cues'], res['plan']
    cada = max(1, int(VP.AFINADO.get('cada', 2) or 2))
    marcados = None
    if mains:                                             # con marcas el efecto va solo en las marcadas: el tema dice cuáles son
        previo = VP.planificar(sub, **kw)
        marcados = {i for i, p in enumerate(previo['plan']) if _base_efecto(p.get('tipo')) in VP.DURACION}
    quitar = set()

    def pedir(i):
        if i in quitar:
            return False
        if marcados is not None:
            return efecto if i in marcados else False
        return efecto if i % cada == cada - 1 else False
    res = VP.planificar(sub, efectos=_Efectos(pedir), **kw)
    if marcados is None:
        for _vuelta in range(2):                          # un efecto pedido que no cabía bajaba a «shatter»: en un look de otro efecto, pila
            ajenos = {i for i, p in enumerate(res['plan']) if _base_efecto(p.get('tipo')) in VP.DURACION and _base_efecto(p.get('tipo')) != efecto} - quitar
            if not ajenos:
                break
            quitar |= ajenos
            res = VP.planificar(sub, efectos=_Efectos(pedir), **kw)
    if res['cues'] and not any(str(r.get('k', '')).startswith(efecto) for c in res['cues'] for r in (c.get('runs') or [])):
        # un tramo de pocos bloques (el tema saca un efecto cada 2) se quedaría sin el look elegido: se pide el efecto en el último bloque
        ultimo = len(res['plan']) - 1
        res = VP.planificar(sub, efectos=_Efectos(lambda i: efecto if i == ultimo else pedir(i)), **kw)
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


# ----------------------------------------------------------------------------------------------------------------------------- los temas enteros (v5.56)
def _tema1(sub, idioma, ancho_tl, alto_tl, ancla, mains, fin, contador):
    """Un tramo del Tema 1 como su GO (kit=True: la composición del kit con Text+), con la receta siguiendo por todo el video."""
    res = KP.planificar(sub, idioma=idioma, ancho_tl=ancho_tl, alto_tl=alto_tl, ancla=ancla, mains=mains,
                        recetas=_Ciclo(range(len(KP.RECETAS)), contador), fin_video=fin, kit=True)
    return res['cues'], res['plan']


def _tema3(sub, idioma, ancho_tl, alto_tl, ancla, mains, fin, estado):
    """Un tramo del Tema 3 como su GO, con el ritmo y el orden de los efectos siguiendo por todo el video (con marcas, el tema decide solo)."""
    efectos = None if mains else _EfectosTema3(estado['t3'])
    res = VP.planificar(sub, idioma=idioma, ancho_tl=ancho_tl, alto_tl=alto_tl, ancla=ancla, mains=mains, efectos=efectos, fin_video=fin)
    _cerrar_tema3(estado['t3'], res['plan'])
    if VP.ROTAR_COLORES:                                  # (el tema va con un solo juego de colores desde la v5.5.4: hoy no rota)
        _rotar_colores(res['cues'], estado['colores'])
    return res['cues'], res['plan']


def _a_su_hora(c, dichas, fin_ajeno, anterior=None, exactas=True):
    """Un bloque que su tema hizo esperar (GP._respiro en el Tema 2; VP._retrasar en el Tema 3 con voz muy rápida) hasta casi el tramo de OTRO tema
    se quedaría en un relámpago o, peor, entraría DESPUÉS que el primer bloque del otro tema (v5.56: el «Ganas» del Tema 2 dejaba al Tema 1 en 0,1 s
    y sin sus palabras). Entra antes: lo más tarde que deja MIN_BORDE antes del otro tema, pero nunca antes de que se diga su primera palabra ni
    antes de que el bloque de antes del mismo tramo (`anterior`) haya durado MIN_BORDE y su última palabra se haya visto MIN_BORDE / 2. Cada
    palabra que esperaba con él entra cuando se dice: la última vez que se dijo antes de que entrara el bloque (así nunca antes de decirse; si no
    se encuentra, con la de antes). `dichas`: las palabras de entrada del bloque (exactas=True, temas «guion») o las de su tramo (Temas 1 y 3).
    Nunca se mueve a más tarde ni toca lo que no esperaba."""
    ini = float(c['start'])
    tope = float(fin_ajeno) - GAP - MIN_BORDE              # lo más tarde que puede entrar sin hacer esperar al otro tema
    if ini <= tope + 1e-9:
        return
    dichas = [(GP._plano(str(w.get('word', ''))), float(w['start'])) for w in dichas or [] if isinstance(w.get('start'), (int, float))]
    if not dichas:
        return

    def primera(texto):
        toks = str(texto or '').split()
        return GP._plano(toks[0]) if toks else ''

    def cuando(texto):
        p = primera(texto)
        veces = [t for q, t in dichas if p and q == p and t <= ini + 0.05]
        return max(veces) if veces else None
    esperaban = [r for r in c.get('runs') or [] if isinstance(r.get('t'), (int, float)) and abs(float(r['t']) - ini) <= 1e-6]
    momentos = {id(r): cuando(r.get('texto')) for r in esperaban if r.get('texto')}
    if exactas:
        suelo = min(t for _q, t in dichas)
    else:
        conocidos = [m for m in momentos.values() if m is not None]
        if not conocidos:
            return
        suelo = min(conocidos)
    if anterior is not None:
        entradas = [float(r['t']) for r in anterior.get('runs') or [] if isinstance(r.get('t'), (int, float))]
        suelo = max(suelo, float(anterior['start']) + MIN_BORDE, max(entradas, default=float(anterior['start'])) + MIN_BORDE / 2.0)
    nuevo = round(min(ini, max(tope, suelo)), 3)
    if nuevo >= ini - 1e-9:
        return
    c['start'] = nuevo
    previo = nuevo
    for r in c.get('runs') or []:
        t = r.get('t')
        if not isinstance(t, (int, float)):
            continue
        if abs(float(t) - ini) <= 1e-6:                   # esperaba con el bloque
            m = momentos.get(id(r))
            r['t'] = round(max(nuevo, m if m is not None else previo), 3)
        previo = max(previo, float(r['t']))
    for l in c.get('lines') or []:                        # las líneas de los Temas 1 y 3: con su primera palabra (la de la clave, con la clave)
        if isinstance(l, dict) and isinstance(l.get('start'), (int, float)) and abs(float(l['start']) - ini) <= 1e-6:
            planos = {GP._plano(x) for x in str(l.get('text') or '').split()}
            suyos = [r for r in c.get('runs') or [] if r.get('texto') and primera(r['texto']) in planos and isinstance(r.get('t'), (int, float))]
            if l.get('role') == 'main':
                suyos = [r for r in suyos if 'fina' not in str(r.get('k', '')) and 'label' not in str(r.get('k', ''))] or suyos
            l['start'] = round(min((float(r['t']) for r in suyos), default=nuevo), 3)


def _guion_entero(look, grupo, palabras, idioma, ancho_tl, ancla, mains, video):
    """Los Temas 2, 4, 5 y 6 enteros: UNA llamada a su planificador (GP.cues_de: Referencia, o tema4_planificador para Tema4/5/6) con las palabras
    de los tramos de `grupo` seguidas, cada tramo cerrado con 'fin_frase'. -> [(cue, n de tramo)] (el tramo, por la primera palabra del bloque).
    Un bloque que el tema hizo esperar hasta el tramo de otro tema entra antes, cuando se dice (_a_su_hora)."""
    lista, de_quien, marcas = [], [], []
    for t in grupo:
        base = len(lista)
        for i in range(t['i0'], t['i1'] + 1):
            lista.append(dict(palabras[i]))               # (copias: las palabras del usuario no se tocan)
            de_quien.append(t['n'])
        if len(lista) > base:
            lista[-1]['fin_frase'] = True
        marcas += _mains_tramo(mains, palabras, t['i0'], t['i1'], desplazar=base)
    if not lista:
        return []
    kw = {'ancla': ancla, 'mains': marcas or None, 'fin_video': grupo[-1]['fin']}
    if look['pack'] != 'Referencia':
        kw['video'] = video                               # (el Tema 5 saca de él el color de la frase clave)
    cues, plan = GP.cues_de(lista, idioma, look['pack'], ancho_tl, **kw)
    por_n = {t['n']: t for t in grupo}
    salida = []
    for k, c in enumerate(cues):
        orig = (plan[k].get('orig') if k < len(plan) and isinstance(plan[k], dict) else None) or []
        j = orig[0] if orig else None
        n = de_quien[j] if isinstance(j, int) and 0 <= j < len(de_quien) else _tramo_por_tiempo(grupo, c)
        t = por_n.get(n)
        if t is not None and t.get('fin_ajeno') is not None:
            anterior = salida[-1][0] if salida and salida[-1][1] == n else None
            _a_su_hora(c, [lista[i] for i in orig if isinstance(i, int) and 0 <= i < len(lista)], t['fin_ajeno'], anterior)
        salida.append((c, n))
    return salida


def _de_una_vez(look, palabras, idioma, ancho_tl, alto_tl, anclas, mains, fin_video, video):
    """UN solo tema entero: el video de una vez, igual que el tema solo (sin tramos que reinicien nada)."""
    m = [x for x in (mains or []) if x is not None and not isinstance(x, bool)] or None
    if look['motor'] == 'kinetic':
        return KP.planificar(palabras, idioma=idioma, ancho_tl=ancho_tl, alto_tl=alto_tl, ancla=anclas['kinetic'], mains=m, fin_video=fin_video, kit=True)['cues']
    if look['id'] in PLANIFICADOR_PROPIO:                 # el Tema 5 (v5.76) y los Estilos 8 y 9 (v5.80)
        import importlib
        kp = importlib.import_module(PLANIFICADOR_PROPIO[look['id']])
        return kp.planificar(palabras, idioma=idioma, ancho_tl=ancho_tl, alto_tl=alto_tl, mains=m, fin_video=fin_video)['cues']
    if look['id'] == 't7':                                # v5.78: el Estilo 7 (como su GO)
        import linea_planificador as LP
        return LP.planificar(palabras, idioma=idioma, ancho_tl=ancho_tl, alto_tl=alto_tl, ancla=anclas['viral'], mains=m, fin_video=fin_video, perfil=LP.ROJO)['cues']
    if look['motor'] == 'viral':
        return VP.planificar(palabras, idioma=idioma, ancho_tl=ancho_tl, alto_tl=alto_tl, ancla=anclas['viral'], mains=m, fin_video=fin_video)['cues']
    kw = {'ancla': anclas['guion'], 'mains': m, 'fin_video': fin_video}
    if look['pack'] != 'Referencia':
        kw['video'] = video
    return GP.cues_de(palabras, idioma, look['pack'], ancho_tl, **kw)[0]


def _tramo_por_tiempo(info, c):
    """El tramo (de `info`) en el que empieza el bloque: el último que empezó antes (con 0,1 s de margen por el adelanto de la entrada)."""
    t = float(c.get('start', 0) or 0) + 0.1
    n = info[0]['n']
    for u in info:
        if u['inicio'] is not None and float(u['inicio']) <= t:
            n = u['n']
    return n


# ----------------------------------------------------------------------------------------------------------------------------- el planificador
def _elegidos(looks):
    """Los looks válidos de la lista, en su orden y sin repetir (un tema repetido no se acepta)."""
    if isinstance(looks, str):
        looks = [looks]
    salida, vistos = [], set()
    for i in looks or []:
        i = str(i or '').strip()
        if i in vistos:
            continue
        l = look_de(i)
        if l is not None:
            vistos.add(i)
            salida.append(l)
    return salida


def _vacio():
    return {'kinetic': [], 'guion': [], 'orden': [], 'tramos': [], 'packs': _Packs(), 'packs_kinetic': [], 'packs_guion': [], 'motores': set(), 'contadores': {}}


def _poner_fin(c, fin):
    """El bloque acaba en `fin` (y sus elementos con fin propio, como mucho ahí)."""
    c['end'] = round(float(fin), 3)
    for r in c.get('runs') or []:
        if isinstance(r.get('fin'), (int, float)) and r['fin'] > c['end']:
            r['fin'] = c['end']


def _recortar(c, limite, tope=None):
    """(Looks sueltos de los packs de antes, como siempre) El bloque acaba como mucho en `limite` y dura al menos MIN_VIEJO; si así pisaría `tope`
    (el principio del bloque siguiente), acaba en `tope` aunque dure menos. Sus elementos con fin propio, igual."""
    if float(c['end']) > limite:
        fin = max(float(c['start']) + MIN_VIEJO, limite)
        if tope is not None and fin > tope:
            fin = max(float(tope), float(c['start']) + 0.1)
        _poner_fin(c, fin)


def _acortar(c, limite):
    """(Temas enteros) El bloque acaba como mucho en `limite` (GAP antes del tramo de otro tema) sin quedarse en menos de MIN_BORDE y sin
    alargarse nunca: si aun así pisa al primer bloque del otro tema, ese espera un poco para entrar (_sin_pisarse)."""
    fin = float(c['end'])
    if fin > limite:
        _poner_fin(c, min(fin, max(float(c['start']) + MIN_BORDE, limite)))


def _retrasar(c, nuevo):
    """El bloque entra más tarde, en `nuevo`: sus palabras (y sus líneas) que entraban antes entran con él (como hace GP._respiro)."""
    c['start'] = round(float(nuevo), 3)
    for r in c.get('runs') or []:
        if isinstance(r.get('t'), (int, float)) and r['t'] < c['start']:
            r['t'] = c['start']
    for l in c.get('lines') or []:
        if isinstance(l, dict) and isinstance(l.get('start'), (int, float)) and l['start'] < c['start']:
            l['start'] = c['start']


def _espera_posible(sig, siguiente):
    """Hasta cuándo puede esperar para entrar el bloque `sig`: ESPERA_MAX como mucho, sin perder más de un tercio de su tiempo ni quedarse él en
    menos de MIN_BORDE (contando con que acabará antes del bloque que va detrás de él, `siguiente`) y sin dejar sus efectos del Tema 3 por debajo
    de su mínimo (VP.MINIMO)."""
    ini, fin = float(sig['start']), float(sig['end'])
    if siguiente is not None:
        fin = min(fin, float(siguiente['start']) - GAP)
    tope = min(ini + ESPERA_MAX, ini + max(0.0, fin - ini) / 3.0, fin - MIN_BORDE)
    for r in sig.get('runs') or []:
        base = _base_efecto(r.get('k'))
        if base in VP.MINIMO and isinstance(r.get('t'), (int, float)):
            tope = min(tope, max(float(r['t']), fin - float(VP.MINIMO[base])))
    return max(ini, tope)


def _separar(c, sig, hueco, siguiente=None):
    """Que el bloque `c` acabe `hueco` s antes de que entre `sig` (el que va detrás). Si así se quedaría en un relámpago (menos de MIN_BORDE, o su
    última palabra casi sin verse), `sig` espera para entrar lo que haga falta y pueda (_espera_posible), como hace el Tema 2 entre sus bloques; y si
    ni así, `c` se queda en lo que quepa (al menos 0,1 s)."""
    limite = float(sig['start']) - hueco
    fin = float(c['end'])
    if fin <= limite + 1e-9:
        return
    ini = float(c['start'])
    entradas = [float(r['t']) for r in c.get('runs') or [] if isinstance(r.get('t'), (int, float))]
    quiere = min(fin, max(ini + MIN_BORDE, max(entradas, default=ini) + MIN_BORDE / 2.0))
    if limite < quiere - 1e-9:
        nuevo = min(quiere + hueco, _espera_posible(sig, siguiente))
        if nuevo > float(sig['start']) + 1e-9:
            _retrasar(sig, nuevo)
            limite = float(sig['start']) - hueco
    _poner_fin(c, max(limite, min(fin, ini + 0.1)))


def _sin_pisarse(salida, looks):
    """Que en pantalla no se vean dos bloques a la vez (`salida` = [(motor, cue, n)] por tramos y, dentro de cada uno, por inicio; looks[k] = el
    look del bloque k):
      · Entre bloques de temas DISTINTOS, el que sale acaba GAP antes de que entre el otro, sin quedarse en un relámpago (_separar).
      · Dentro de un tema entero manda el tema: sus huecos (0-0,02 s en el Tema 2, que va «sin hueco en negro» desde la v5.50) no se tocan; solo
        si un bloque pisa al siguiente del mismo tema, acaba cuando entra él.
      · Los looks sueltos de los packs de antes, como siempre: GAP con el bloque siguiente (sea del tema que sea), sin bajar de MIN_VIEJO."""
    n = len(salida)
    otro = [None] * n                                     # otro[k] = el primer bloque de detrás que es de OTRO tema
    for k in range(n - 2, -1, -1):
        otro[k] = k + 1 if looks[k + 1]['id'] != looks[k]['id'] else otro[k + 1]
    for k in range(n):
        c, look = salida[k][1], looks[k]
        if not look.get('entero'):
            if k + 1 < n:
                t_sig = float(salida[k + 1][1]['start'])
                _recortar(c, t_sig - GAP, t_sig)
            continue
        if k + 1 < n and looks[k + 1]['id'] == look['id']:
            _separar(c, salida[k + 1][1], 0.0, salida[k + 2][1] if k + 2 < n else None)
        j = otro[k]
        if j is not None:
            _separar(c, salida[j][1], GAP, salida[j + 1][1] if j + 1 < n else None)


def _sin_emojis(c):
    """v5.56: ningún bloque sale de aquí con emoji (sin la Edición PRO no hay emojis: GO los pone después, si tocan, con su regla)."""
    for d in [c] + list(c.get('runs') or []) + list(c.get('lines') or []):
        if isinstance(d, dict):
            for k in [k for k in d if str(k).startswith('emoji')]:
                d.pop(k, None)


def _etiqueta(motor, c):
    """Lo que enseña un bloque, para el resumen: la receta (Tema 1), el efecto (Tema 3) o el estilo (temas «guion»; * = lleva palabra grande)."""
    if motor == 'kinetic':
        return str(c.get('plantilla') or '?')
    if motor == 'viral':
        if any(r.get('k') == 'v tipo' for r in c.get('runs') or []):
            return 'tipo'
        if any(str(r.get('k') or '').startswith('v rojo') for r in c.get('runs') or []):
            return 'rojo'
        if any(str(r.get('k') or '').startswith('v ambar') for r in c.get('runs') or []):
            return 'ambar'                                # v5.80: el Estilo 8
        if any(str(r.get('k') or '').startswith('v edi') for r in c.get('runs') or []):
            return 'editorial'                            # v5.80: el Estilo 9
        efectos = [_base_efecto(r.get('k')) for r in c.get('runs') or [] if _base_efecto(r.get('k')) in VP.DURACION]
        return efectos[0] if efectos else 'pila'
    grande = any(r.get('rol') == 'main' for r in c.get('runs') or [])
    return f"e{c.get('estilo')}" + ('*' if grande else '')


def planificar(palabras, looks, idioma='es', ancho_tl=1080, alto_tl=1920, ancla_kinetic='bajo', ancla_viral='bajo', ancla_guion='medio', mains=None, fin_video=None,
               video=None):
    """palabras [{'word','start','end'}] y `looks` (ids en el orden en que se turnan: temas enteros 't1'…'t6' y/o looks sueltos de antes) → ver el
    docstring del módulo. `mains`: las marcas «Principal» de Creativo (índices de `palabras` o textos); `video`: la ruta del video (Tema 5)."""
    elegidos = _elegidos(looks)
    if not elegidos or not palabras:
        return _vacio()
    partes = tramos(palabras)
    if not partes:
        return _vacio()
    info = []
    for n, (i0, i1) in enumerate(partes):
        inicio = palabras[i0].get('start')
        info.append({'n': n, 'i0': i0, 'i1': i1, 'look': elegidos[n % len(elegidos)], 'inicio': float(inicio) if inicio is not None else None})
    for n, t in enumerate(info):
        t['fin'] = info[n + 1]['inicio'] if n + 1 < len(info) else fin_video        # el último bloque del tramo no pisa el tramo siguiente
        sig = next((u for u in info[n + 1:] if u['look']['id'] != t['look']['id']), None)
        t['fin_ajeno'] = sig['inicio'] if sig is not None else None                 # (con un solo look, y al final del video, manda el tema: fin_video)
    estado = {'t1': [0], 't3': {'bloques': 0, 'rot': 0}, 'barrido': [0], 'colores': {}}
    salida = []                                           # [(motor, cue, n de tramo)]
    if len(elegidos) == 1 and elegidos[0].get('entero'):
        look = elegidos[0]
        anclas = {'kinetic': ancla_kinetic, 'viral': ancla_viral, 'guion': ancla_guion}
        for c in _de_una_vez(look, palabras, idioma, ancho_tl, alto_tl, anclas, mains, fin_video, video):
            salida.append((look['motor'], c, _tramo_por_tiempo(info, c)))
    else:
        juntos = {}                                       # id del tema «guion» entero -> sus tramos (se planifican juntos)
        for t in info:
            look = t['look']
            if look.get('entero') and look['motor'] == 'guion':
                juntos.setdefault(look['id'], []).append(t)
                continue
            sub = palabras[t['i0']:t['i1'] + 1]
            m_sub = _mains_tramo(mains, palabras, t['i0'], t['i1']) or None
            if look.get('entero') and look['motor'] == 'kinetic':
                cues, _plan = _tema1(sub, idioma, ancho_tl, alto_tl, ancla_kinetic, m_sub, t['fin'], estado['t1'])
            elif look['id'] in PLANIFICADOR_PROPIO:       # v5.76: el Tema 5 nuevo; v5.80: los Estilos 8 y 9; tramo a tramo (sus bloques no dependen de los de antes)
                import importlib
                kp_t = importlib.import_module(PLANIFICADOR_PROPIO[look['id']])
                res_t = kp_t.planificar(sub, idioma=idioma, ancho_tl=ancho_tl, alto_tl=alto_tl, mains=m_sub, fin_video=t['fin'])
                cues, _plan = res_t['cues'], res_t['plan']
            elif look['id'] == 't7':                      # v5.78: el Estilo 7, tramo a tramo
                import linea_planificador as LP
                res_r = LP.planificar(sub, idioma=idioma, ancho_tl=ancho_tl, alto_tl=alto_tl, ancla=ancla_viral, mains=m_sub, fin_video=t['fin'], perfil=LP.ROJO)
                cues, _plan = res_r['cues'], res_r['plan']
            elif look.get('entero'):
                cues, _plan = _tema3(sub, idioma, ancho_tl, alto_tl, ancla_viral, m_sub, t['fin'], estado)
            elif look['motor'] == 'kinetic':
                cues, _plan = _cues_kinetic(sub, look, idioma, ancho_tl, alto_tl, ancla_kinetic, m_sub, t['fin'])
            elif look.get('efecto') == 'v linea':        # v5.75: la línea con la caja azul (linea_planificador; el color lo pone el «color principal»)
                import linea_planificador as LP
                res_l = LP.planificar(sub, idioma=idioma, ancho_tl=ancho_tl, alto_tl=alto_tl, ancla=ancla_viral, fin_video=t['fin'], clip_activa=LP.CLIP_ACTIVA_CREA)
                cues, _plan = res_l['cues'], res_l['plan']
            elif look['motor'] == 'viral':
                cues, _plan = _cues_viral(sub, look, idioma, ancho_tl, alto_tl, ancla_viral, m_sub, t['fin'])
                _rotar_colores(cues, estado['colores'])   # (los looks sueltos de antes, como siempre)
            else:
                cues, _plan = _cues_guion(sub, look, idioma, ancho_tl, ancla_guion, m_sub, t['fin'], estado['barrido'])
            if t['fin_ajeno'] is not None:                # (un bloque que su tema hizo esperar hasta el tramo de otro tema entra antes)
                anterior = None
                for c in sorted(cues, key=lambda c: float(c.get('start', 0) or 0)):
                    _a_su_hora(c, sub, t['fin_ajeno'], anterior, exactas=False)
                    anterior = c
            for c in cues:
                salida.append((look['motor'], c, t['n']))
        for grupo in juntos.values():
            con_marcas = any(_mains_tramo(mains, palabras, t['i0'], t['i1']) for t in grupo)
            for trozo in ([[t] for t in grupo] if con_marcas else [grupo]):
                for c, n in _guion_entero(trozo[0]['look'], trozo, palabras, idioma, ancho_tl, ancla_guion, mains, video):
                    salida.append(('guion', c, n))
    por_n = {t['n']: t for t in info}
    for _m, c, n in salida:
        t = por_n[n]
        c['pack'] = pack_de_look(t['look'])
        if t['fin_ajeno'] is not None:
            if t['look'].get('entero'):
                _acortar(c, float(t['fin_ajeno']) - GAP)
            else:
                _recortar(c, float(t['fin_ajeno']) - GAP)
        _sin_emojis(c)
    if not (len(elegidos) == 1 and elegidos[0].get('entero')):       # (un solo tema entero: tal cual lo hace el tema)
        salida.sort(key=lambda x: (x[2], float(x[1].get('start', 0) or 0)))     # los bloques de un tramo, siempre antes que los del siguiente
        _sin_pisarse(salida, [por_n[n]['look'] for _m, _c, n in salida])
        import tipo_planificador as TP
        TP.reajustar([c for _m, c, _n in salida])      # (un «v tipo» que tuvo que esperar: sus palabras siguen saliendo cuando se dicen)
    salida.sort(key=lambda x: float(x[1].get('start', 0) or 0))
    bloques_de, detalle = {}, {}
    for m, c, n in salida:
        bloques_de[n] = bloques_de.get(n, 0) + 1
        detalle.setdefault(n, []).append(_etiqueta(m, c))
    resumen_ = [{'tramo': t['n'], 'look': t['look']['id'], 'pack': pack_de_look(t['look']), 'tema': t['look'].get('tema'), 'motor': t['look']['motor'],
                 'palabras': t['i1'] - t['i0'] + 1, 'bloques': bloques_de.get(t['n'], 0), 'i0': t['i0'], 'i1': t['i1'], 'inicio': t['inicio'], 'fin': t['fin'],
                 'detalle': detalle.get(t['n'], [])} for t in info]
    en_orden = []                                         # los packs con algún bloque, en el orden del usuario
    for look in elegidos:
        p = pack_de_look(look)
        if p not in en_orden and any(pack_de_look(t['look']) == p and bloques_de.get(t['n']) for t in info):
            en_orden.append(p)
    motores = {m for m, _c, _n in salida}
    orden = [(m, c) for m, c, _n in salida]
    return {'kinetic': [c for m, c in orden if m in ('kinetic', 'viral')], 'guion': [c for m, c in orden if m == 'guion'], 'orden': orden, 'tramos': resumen_,
            'packs': _Packs(en_orden, motores), 'packs_kinetic': [p for p in en_orden if MOTOR_DE_PACK.get(p, 'guion') != 'guion'],
            'packs_guion': [p for p in en_orden if MOTOR_DE_PACK.get(p, 'guion') == 'guion'], 'motores': motores,
            'contadores': {'recetas_t1': estado['t1'][0], 'bloques_t3': estado['t3']['bloques'], 'rotacion_t3': estado['t3']['rot'], 'barridos_t2': estado['barrido'][0]}}


def renombrar_packs(res, nombres):
    """GO con un estilo personalizado (pack_personalizado.preparar): cambia en el plan el pack BASE de cada tema por su pack derivado
    ({'VIRAL': 'VIRAL · a1b2c3'}): el c['pack'] de cada bloque y las listas de packs. Lo que no está en `nombres` se queda. Devuelve `res`."""
    nombres = {str(k): str(v) for k, v in (nombres or {}).items() if k and v}
    if not nombres or not res:
        return res
    for _m, c in res.get('orden') or []:
        if c.get('pack') in nombres:
            c['pack'] = nombres[c['pack']]
    for clave in ('packs_kinetic', 'packs_guion'):
        res[clave] = [nombres.get(p, p) for p in res.get(clave) or []]
    viejos = res.get('packs') or ()
    res['packs'] = _Packs([nombres.get(p, p) for p in viejos], getattr(viejos, 'motores', ()))
    return res


# ----------------------------------------------------------------------------------------------------------------------------- el estilo del usuario en el disco
MAX_LOOKS = 8                                       # los looks que rotan en un pack de antes (más no se nota: un tramo dura 3-5 s)
CLAVES_AJUSTES = ('fuente_principal', 'fuente_secundaria', 'color_principal', 'color_secundario')
_HEX = re.compile(r'#?([0-9a-fA-F]{6})')
_RESERVADOS = ('auto', 'media_pool')                # (plantillas.buscar_pack los trata aparte)


def tr(texto, /, **valores):
    """i18n.tr sin cargarlo al importar este módulo (lo importan los hilos de dibujo de las vistas); sin i18n, el texto en español."""
    try:
        from i18n import tr as traducir
    except Exception:
        return texto.format(**valores) if valores else texto
    return traducir(texto, **valores)


def ajustes_vacios():
    """Los ajustes de un estilo con todo «lo del tema»."""
    return {k: '' for k in CLAVES_AJUSTES}


def _parte(clave):
    """El nombre que ve el usuario de la parte del texto de un ajuste."""
    return tr('Texto principal') if clave.endswith('principal') else tr('Arriba y abajo')


def _fuente_valida(valor, clave):
    if valor is None:
        return ''
    if isinstance(valor, (list, tuple)):                  # (también [familia, estilo], la forma de fuente_usuario)
        valor = '|'.join(str(x) for x in valor)
    valor = valor.strip() if isinstance(valor, str) else None
    if valor == '':
        return ''
    partes = [p.strip() for p in valor.split('|')] if valor else []
    if not partes or len(partes) > 2 or not partes[0]:
        raise ValueError(tr('La letra de «{c}» no es válida (va como "Familia|Estilo").', c=_parte(clave)))
    familia = partes[0]
    estilo = partes[1] if len(partes) == 2 and partes[1] else 'Regular'
    if len(familia) > 100 or len(estilo) > 60 or any(ord(ch) < 32 for ch in familia + estilo):
        raise ValueError(tr('La letra de «{c}» no es válida (va como "Familia|Estilo").', c=_parte(clave)))
    return f'{familia}|{estilo}'


def _color_valido(valor, clave):
    if valor is None:
        return ''
    m = _HEX.fullmatch(valor.strip()) if isinstance(valor, str) else None
    if isinstance(valor, str) and not valor.strip():
        return ''
    if not m:
        raise ValueError(tr('El color de «{c}» no es válido (va como "#RRGGBB").', c=_parte(clave)))
    return '#' + m.group(1).upper()


def normalizar_ajustes(ajustes=None):
    """Los ajustes del estilo del usuario (se guardan EN EL PACK): {'fuente_principal': "Familia|Estilo" o "", 'fuente_secundaria': …,
    'color_principal': "#RRGGBB" o "", 'color_secundario': …}. Vacío = lo del tema; principal = la palabra grande (rol main); secundaria = el
    texto de arriba y abajo. Devuelve las cuatro claves, normalizadas ("familia" sola -> "familia|Regular"; "#ff0000" -> "#FF0000").
    ValueError si sobra una clave o un valor no vale."""
    if ajustes is None:
        return ajustes_vacios()
    if not isinstance(ajustes, dict):
        raise ValueError(tr('Los ajustes del estilo no son válidos.'))
    raras = [k for k in ajustes if k not in CLAVES_AJUSTES]
    if raras:
        raise ValueError(tr('Ajuste desconocido: {k}', k=raras[0]))
    salida = ajustes_vacios()
    for k in ('fuente_principal', 'fuente_secundaria'):
        salida[k] = _fuente_valida(ajustes.get(k), k)
    for k in ('color_principal', 'color_secundario'):
        salida[k] = _color_valido(ajustes.get(k), k)
    return salida


def _dibujable(id_):
    """¿Sabe mezcla_vista dibujar este look? (los Temas 1-3 y los looks sueltos; los Temas 4-6 los dibujaría como el 2)."""
    return ':' in str(id_) or str(id_) in ('t1', 't2', 't3')


def _guardar_poster(carpeta, ids, poster=None):
    """vista_mezcla.jpg, la foto de la tarjeta del estilo: `poster` (PIL.Image o ruta: la imagen de la fila) o, si todos sus temas los sabe dibujar
    mezcla_vista, la suya. Si no hay ninguna, se quita la vieja (la tarjeta no enseña un estilo que ya no es). -> la ruta o None."""
    ruta = Path(carpeta) / 'vista_mezcla.jpg'
    try:
        if poster is not None:
            from PIL import Image
            if hasattr(poster, 'save'):
                im = poster.convert('RGB')
            else:
                with Image.open(poster) as abierta:
                    im = abierta.convert('RGB')
            im.save(ruta, quality=88)
            return ruta
        if ids and all(_dibujable(i) for i in ids):
            import mezcla_vista
            mezcla_vista.poster(list(ids), foto=0, ancho=540).save(ruta, quality=88)
            return ruta
    except Exception:
        pass
    try:
        if ruta.is_file():
            ruta.unlink()
    except OSError:
        pass
    return None


def _nombre_del_estilo(nombre):
    nombre = re.sub(r'\s+', ' ', str(nombre or '')).strip()[:40].strip()
    return nombre or 'Mi estilo'


def _nombre_reservado(nombre):
    """¿Es el nombre (o la carpeta) de un pack que viene con el programa? Un estilo que se llamara así lo REEMPLAZARÍA en la lista
    (plantillas._listar_packs) y buscar_pack lo encontraría antes que al de fábrica."""
    import plantillas
    nombres = set(plantillas.FABRICA) | set(plantillas.FABRICA.values()) | {plantillas.NOMBRE_INCORPORADO} | set(_RESERVADOS)
    try:
        nombres |= {p.nombre for p in plantillas.packs_incorporados()}
    except Exception:
        pass
    claves = {str(n).casefold() for n in nombres} | {plantillas.nombre_seguro(n).casefold() for n in nombres}
    return nombre.casefold() in claves or plantillas.nombre_seguro(nombre).casefold() in claves


def _es_pack_ajeno(carpeta):
    """¿La carpeta ya tiene un pack que NO es un estilo de «Crea tu estilo» (un pack importado, con sus .drb)? Ese no se pisa."""
    import archivos_seguros
    carpeta = Path(carpeta)
    if not carpeta.is_dir():
        return False
    datos = archivos_seguros.leer_json(carpeta / 'pack.json', None)
    if isinstance(datos, dict) and datos:
        return not (datos.get('guion') == 'mezcla' or datos.get('base'))       # un estilo nuestro (mezcla o derivado) sí se puede rehacer
    if (carpeta / 'estilos.json').is_file():
        return True
    try:
        return any(p.suffix.lower() in ('.drb', '.drt') for p in carpeta.iterdir())
    except OSError:
        return False


def crear_estilo(nombre, temas, ajustes=None, carpeta_packs=None, poster=None, base_texto=None):
    """v5.56 «Crea tu estilo»: guarda el estilo del usuario como un pack (CONTRATO 3) en carpeta_de_packs()/nombre_seguro(nombre):
        2 o más:   {"version": 2, "nombre", "guion": "mezcla", "looks": ["t2:6", "t3:select", "t5"] (orden de toque), "formatos": {"v": {"mezcla": true}}, "ajustes"}
        1 tema entero: {"version": 2, "nombre", "base": "VIRAL", "ajustes"}   (pack DERIVADO: GO lo trata como ese tema con sus ajustes, no como mezcla)
        1 look suelto: una mezcla de un solo look (todo el video con ese efecto)
    `temas`: ids sin repetir: temas enteros 't1'…'t6' o (v5.75) los looks de los principales ('t2:6', 't3:select'…, ver PRINCIPALES_CREA);
    `ajustes`: ver normalizar_ajustes(); `base_texto`: el id de la base elegida (BASES_CREA) o None: su letra va en 'fuente_secundaria' (si el
    usuario no eligió otra) y su id se guarda en el pack ('base_texto') para la nota de la tarjeta; `poster`: la foto de la tarjeta (PIL.Image o ruta).
    Escribe con archivos_seguros y avisa a plantillas (invalidar_packs). Llamarlo fuera del hilo de la interfaz (escribe en el disco y puede dibujar
    la foto). -> (nombre, carpeta). ValueError (con el texto para el usuario) si los temas, los ajustes o el nombre no valen."""
    import archivos_seguros
    import plantillas
    if isinstance(temas, str):
        temas = [temas]
    ids = [str(i or '').strip() for i in (temas or [])]
    if not ids:
        raise ValueError(tr('Elige al menos un texto principal.'))
    for i in ids:
        if not es_tema_entero(i) and principal_crea(i) is None:
            raise ValueError(tr('No conozco el estilo «{t}».', t=i))
    if len(set(ids)) != len(ids):
        raise ValueError(tr('Cada texto principal va una sola vez.'))
    if len(ids) > len(PRINCIPALES_CREA):
        raise ValueError(tr('Como mucho {n} textos principales.', n=len(PRINCIPALES_CREA)))
    texto_base = base_crea(base_texto) if base_texto else None
    if base_texto and texto_base is None:
        raise ValueError(tr('No conozco el texto base «{t}».', t=base_texto))
    ajustes = dict(ajustes or {})
    if texto_base and not str(ajustes.get('fuente_secundaria') or '').strip():
        ajustes['fuente_secundaria'] = texto_base['fuente']
    ajustes = normalizar_ajustes(ajustes)
    nombre = _nombre_del_estilo(nombre)
    if _nombre_reservado(nombre):
        raise ValueError(tr('«{n}» es el nombre de un estilo del programa: elige otro.', n=nombre))
    base = Path(carpeta_packs) if carpeta_packs else plantillas.carpeta_de_packs()
    carpeta = base / plantillas.nombre_seguro(nombre)          # la misma carpeta que plantillas.buscar_pack(nombre) mira
    if _es_pack_ajeno(carpeta):
        raise ValueError(tr('Ya hay un pack que se llama «{n}»: elige otro nombre.', n=nombre))
    if len(ids) == 1 and es_tema_entero(ids[0]):
        datos = {'version': 2, 'nombre': nombre, 'base': look_de(ids[0])['pack'], 'ajustes': ajustes}
    else:
        datos = {'version': 2, 'nombre': nombre, 'guion': 'mezcla', 'looks': ids, 'formatos': {'v': {'mezcla': True}}, 'ajustes': ajustes}
    if texto_base:
        datos['base_texto'] = texto_base['id']
    carpeta.mkdir(parents=True, exist_ok=True)
    archivos_seguros.escribir_json(carpeta / 'pack.json', datos, indent=2)
    _guardar_poster(carpeta, ids, poster)
    try:
        plantillas.invalidar_packs()
    except Exception:
        pass
    return nombre, carpeta


def crear_pack(nombre, looks, carpeta_packs=None):
    """(Packs de antes) Guarda «Mi estilo» como un pack de mezcla: solo `pack.json` ({"guion": "mezcla", "looks": [...]}) y la foto de muestra de su
    tarjeta (vista_mezcla.jpg). No lleva clips propios: al generar, cada tema pone los suyos (los .drb de fábrica). Devuelve (nombre, carpeta)."""
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
    _guardar_poster(carpeta, ids)
    try:
        plantillas.invalidar_packs()
    except Exception:
        pass
    return nombre, carpeta


def resumen(res):
    """El plan en una tabla legible (para depurar)."""
    filas = ['  tramo look            motor    palabras bloques  detalle']
    for t in res.get('tramos', []):
        filas.append(f"  {t['tramo']:4d} {t['look']:<15s} {t['motor']:<8s} {t['palabras']:8d} {t['bloques']:7d}  {' '.join(t.get('detalle') or [])}")
    return '\n'.join(filas)
