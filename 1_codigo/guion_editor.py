# CineCaptions · By Cinema Productions
# 1_codigo/guion_editor.py — el editor Creativo para el estilo «guion»: las marcas de las palabras → el plan de bloques (el MISMO que usa Generar).
"""
guion_editor.py  (v5.10)
------------------------
Une las marcas del editor Creativo con el planificador del estilo «guion» (guion_planificador.py). El editor y «Generar» llaman a ESTA misma función
(`planear`), así que «Así se verá este bloque» es, por construcción, lo que Generar coloca en la línea de tiempo (el .json de place_guion_track).

Qué significa cada pincel con un pack de estilo «guion» (como «Referencia»):

    Principal  → la palabra GRANDE del bloque (varias seguidas = una sola palabra grande).
    Abajo      → una palabra pequeña en NEGRITA.
    Arriba     → una palabra pequeña en letra FINA (aunque el planificador la habría puesto en negrita).
    Simple     → sin marca: lo decide el planificador (la grande por peso de la palabra, la negrita por ritmo).

Una línea pequeña con alguna palabra «Abajo» lleva en negrita SOLO esas; sin marcas, la negrita se elige sola. El estilo de un bloque que se cambia a mano
(chips «Estilo» de la vista) se guarda en la primera palabra del bloque (w['estilo']) y manda en todas sus palabras grandes.
"""
import guion_captions as G
import guion_planificador as P

ROL_GRANDE, ROL_FINA, ROL_NEGRITA = 'main', 'context', 'complement'


def es_guion(nombre_pack, formato='v'):
    """True si ese pack es de estilo «guion» y sirve para el formato (el estilo palabra a palabra solo existe en vertical)."""
    try:
        import plantillas
        p = plantillas.buscar_pack(nombre_pack or '')
    except Exception:
        return False
    return bool(p is not None and getattr(p, 'guion', None) and not getattr(p, 'kinetic', False) and (formato or 'v') in p.formatos and (formato or 'v') == 'v')


def parametros_de_marcas(palabras, roles):
    """(mains, pesos, estilos_palabra) para el planificador a partir de las marcas del editor (índices = posición en `palabras`)."""
    roles = list(roles or [])
    mains, pesos, estilos = [], {}, {}
    for i, w in enumerate(palabras):
        vacia = not str(w.get('word') or '').strip()
        r = roles[i] if i < len(roles) else None
        if not vacia:
            if r == ROL_GRANDE:
                mains.append(i)
            elif r == ROL_NEGRITA:
                pesos[i] = 'B'
            elif r == ROL_FINA:
                pesos[i] = 'L'
        try:
            if w.get('estilo'):
                estilos[i] = int(w['estilo'])
        except (TypeError, ValueError):
            pass
    return (mains or None), pesos, estilos


def planear(palabras, roles, pack, ancla='medio', fin_video=None, ancho_tl=1080, idioma='es', automatico=False, video=None):
    """El plan completo de bloques para esas palabras y esas marcas.

    Devuelve {'cues': [...] (lo que se escribe en el .json de Resolve), 'plan': [...] (uno por bloque, con 'orig', 'grandes', 'pesos', 'estilos'),
              'indice': [k de bloque de cada palabra (las que no entran, el del bloque anterior)]}.
    automatico=True ignora las marcas de Principal / Arriba / Abajo (lo que haría GO solo); los estilos elegidos a mano se respetan igual.
    video (v5.5.8, Tema 5): el color de la frase clave sale de él."""
    if automatico:
        _m, _p, estilos = parametros_de_marcas(palabras, [])
        mains, pesos = None, {}
    else:
        mains, pesos, estilos = parametros_de_marcas(palabras, roles)
    cues, plan = P.cues_de(palabras, idioma, pack, ancho_tl, ancla=ancla, mains=mains, pesos=pesos, estilos_palabra=estilos, fin_video=fin_video, video=video)
    indice = [-1] * len(palabras)
    for k, b in enumerate(plan):
        for o in b.get('orig', ()):
            if 0 <= o < len(indice):
                indice[o] = k
    previo = 0
    for i, k in enumerate(indice):          # una palabra que no entró en ningún bloque (vacía, tartamudeo) cae donde cae la anterior
        if k < 0:
            indice[i] = previo
        else:
            previo = k
    return {'cues': cues, 'plan': plan, 'indice': indice}


def roles_automaticos(palabras, pack, ancla='medio', fin_video=None, ancho_tl=1080, idioma='es'):
    """Los roles que el planificador elige solo, listos para pintar en el editor: Principal (grande), Abajo (negrita) y None («Simple»: fina/automática).
    Pintarlos NO cambia el resultado: es el mismo que sin marcas; solo deja a la vista lo que decidió el planificador para que se pueda retocar."""
    res = planear(palabras, [], pack, ancla, fin_video, ancho_tl, idioma, automatico=True)
    roles = [None] * len(palabras)
    for b in res['plan']:
        for o in b.get('grandes', ()):
            if 0 <= o < len(roles):
                roles[o] = ROL_GRANDE
        for o, peso in (b.get('pesos') or {}).items():
            if peso == 'B' and 0 <= o < len(roles) and roles[o] is None:
                roles[o] = ROL_NEGRITA
    return roles


def bloques_para_editor(res, palabras):
    """Los bloques con la forma que espera el editor: [{'start', 'end', 'estilo', 'lines': [{'role', 'text', 'start'}], 'cue'}] (+ el índice por palabra).
    Cada palabra (o grupo) es una «línea» con su momento, igual que las que se mandan a los sonidos y a los emojis al generar."""
    bloques = []
    for k, c in enumerate(res['cues']):
        runs = sorted(c['runs'], key=lambda r: r.get('t', 0))
        orig = res['plan'][k].get('orig', ()) if k < len(res['plan']) else ()
        manual = any(0 <= o < len(palabras) and palabras[o].get('estilo') for o in orig)       # el estilo de este bloque lo eligió el usuario
        # el emoji del bloque (el de su primera palabra con emoji), como lo coloca Generar: entra con la palabra grande y dura lo que la pila
        o_emoji = next((o for o in orig if 0 <= o < len(palabras) and palabras[o].get('emoji')), None)
        if o_emoji is not None:
            principal = next((r for r in runs if r.get('rol') == 'main'), None)
            if principal is not None:
                t_emoji = float(principal.get('t', c['start']))                       # con la palabra grande…
            else:                                                                      # …o, sin ella, con la palabra que lleva el emoji (la última línea ya iniciada)
                t_p = float(palabras[o_emoji].get('start') or c['start'])
                ya = [r for r in runs if float(r.get('t', c['start'])) <= t_p + 0.06]
                t_emoji = float((ya[-1] if ya else runs[0]).get('t', c['start']))
            c['emoji'] = palabras[o_emoji]['emoji']
            c['emoji_ini'] = t_emoji
            c['emoji_fin'] = float(c['end'])
        bloques.append({'start': c['start'], 'end': c['end'], 'fin_hablado': c['end'], 'estilo': c.get('estilo'), 'estilo_manual': manual, 'cue': c,
                        'lines': [{'role': {'main': 'main', 'context': 'context', 'complement': 'complement'}.get(r['rol'], 'base'), 'text': r['texto'],
                                   'start': r.get('t', c['start'])} for r in runs]})
    return bloques, res['indice']
