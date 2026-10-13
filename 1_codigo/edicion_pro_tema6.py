# CineCaptions · By Cinema Productions
# 1_codigo/edicion_pro_tema6.py — Tema 6 («Editorial», v5.4.52): el motor del Tema 5 (edicion_pro_tema5.planificar con estilo='editorial') con el
# estilo del video de referencia que trajo el usuario (un reel editorial cálido):
#   * captions: las dos líneas en una serif alta y fina (Instrument Serif), la de lo que se dice pequeña y blanca y la frase clave GRANDE en lima
#     (si pesa: énfasis, cifra o el tema del video) o en blanco; a la altura del pecho; sobre una escena, pequeña y en tinta oscura abajo.
#   * escenas: melocotón cálido a pantalla completa con cartas blancas (borde cálido, la misma serif), entran y salen con un destello blanco.
#   * elementos (Remotion «EditorialT6»): el VISOR de la cámara sobre la cara («tú mismo», «tus ojos», «la cuadrícula»), la BARRA DE BÚSQUEDA que
#     escribe la palabra que hay que comentar, el PERFIL con la cifra de seguidores que se dice y la píldora del EQUIPO bajo el caption.
#   * sin los pasos ni el deslizador de cristal oscuro del Tema 5 (no son de este estilo).
"""
    estilo_video()                    -> el estilo de las escenas (melocotón, a pantalla completa)
    color_clave(palabras, temas)      -> '#DDF25E' (lima) o '#FFFFFF'
    temas_del_video(bloques)          -> las palabras de contenido que se repiten (el tema del video)
    elementos(bl, dur, idioma, libre, det_de, cara_de, usuario, debiles) -> piezas
"""
import re

import edicion_pro_tema5_acomp as AC
import edicion_pro_tema5_escenas as DIR

LIMA = '#DDF25E'
BLANCO = '#FFFFFF'
Y_NORMAL = {True: 52.0, False: 74.0}
Y_ESCENA = 86.0                                    # sobre una escena de objetos: la frase pequeña, en tinta, abajo (como la referencia)
VISOR = [('tu', 'mismo'), ('tu', 'misma'), ('ti', 'mismo'), ('ti', 'misma'), ('yourself',), ('myself',), ('yo', 'mismo'), ('yo', 'misma'),
         ('tus', 'ojos'), ('your', 'eyes'), ('tu', 'cara'), ('your', 'face'), ('cuadricula',), ('grid',), ('encuadre',), ('tu', 'rostro'),
         ('voce', 'mesmo'), ('seus', 'olhos')]
COMENTA = {'comenta', 'comentame', 'comenten', 'comente', 'comment', 'escribe', 'escribeme', 'escriban', 'type', 'write', 'escreva', 'manda', 'mandame',
           'envia', 'enviame', 'dm'}
SEGUIDORES = {'seguidores': 'seguidores', 'followers': 'followers', 'suscriptores': 'suscriptores', 'subscribers': 'subscribers', 'vistas': 'vistas',
              'views': 'views', 'visualizaciones': 'vistas', 'likes': 'likes', 'seguidoras': 'seguidoras', 'inscritos': 'inscritos'}
EQUIPO = {'equipo', 'team', 'clientes', 'clients', 'comunidad', 'community', 'alumnos', 'students', 'socios', 'partners', 'familia', 'family',
          'audiencia', 'audience', 'seguidores', 'followers', 'gente', 'people', 'personas', 'equipe', 'clientas', 'alunos'}
MIL = {'mil': 1000, 'thousand': 1000, 'k': 1000, 'millon': 1000000, 'millones': 1000000, 'million': 1000000, 'millions': 1000000, 'milhao': 1000000}


def _p(t):
    return AC.plegar(t)


def _limpio(t):
    return str(t).strip(' .,;:!?¡¿"\'()[]«»…“”')


def estilo_video():
    return {'fondos': ['melocoton'], 'encima': False, 'partir': False, 'orden': ['completa']}


def temas_del_video(bloques, debiles=frozenset()):
    """Las palabras que salen como frase clave 2 veces o más: el tema del video («content», «cuadrícula»…). Se llama tras marcar las claves."""
    cuenta = {}
    for b in bloques:
        for w in b['palabras']:
            p = _p(w['texto'])
            if w.get('clave') and len(p) >= 4 and p not in DIR.CONECTORAS and p not in debiles:
                cuenta[p] = cuenta.get(p, 0) + 1
    return {p for p, n in cuenta.items() if n >= 2}


def color_clave(palabras, temas, enfasis=frozenset()):
    """La frase clave va en lima si pesa (énfasis, cifra o el tema del video); si no, en blanco (como la referencia: «content team» en lima,
    «great for me» en blanco)."""
    claves = [w for w in palabras if w.get('clave')]
    pesa = any(_p(w['texto']) in enfasis or _p(w['texto']) in temas or re.search(r'\d', w['texto']) for w in claves)
    return LIMA if pesa else BLANCO


def _cifra_con_mil(todas, i):
    """'100' + 'mil' → '100K'; '2,5' + 'millones' → '2.5M'; '10k' → '10K'. None si no es una cifra."""
    c = DIR._cifra(todas[i][2])
    if c is None:
        return None
    valor = c[0].replace(',', '.') if c[0].count(',') == 1 and len(c[0].split(',')[1]) <= 2 else c[0].replace(',', '')
    if c[1] in ('k', 'K'):
        return valor + 'K'
    if c[1] == 'M':
        return valor + 'M'
    if i + 1 < len(todas) and todas[i + 1][1] in MIL:
        return valor + ('K' if MIL[todas[i + 1][1]] == 1000 else 'M')
    return valor


def elementos(bl, dur, idioma='es', libre=None, det_de=None, cara_de=None, usuario='', debiles=frozenset(), caras_de=None):
    """Las piezas propias del Tema 6 (EditorialT6). `caras_de(t)` → las cajas de las caras en ese segundo (fracciones del timeline)."""
    todas = [(b['ini'] + w['t'], _p(w['texto']), w['texto'], n, j) for n, b in enumerate(bl) for j, w in enumerate(b['palabras'])]
    out = []

    def ok(a, z, aire=1.0):
        if libre is not None and not libre(a, z):
            return False
        return not any(a < p['fin'] + aire and p['ini'] - aire < z for p in out)

    # 1) el visor sobre la cara
    ultimo = -99.0
    for i, (t, p, txt, nb, j) in enumerate(todas):
        if len([o for o in out if o['valores']['tipo'] == 'visor']) >= 2 or t - ultimo < 10.0:
            continue
        if not any(tuple(x[1] for x in todas[i:i + len(f)]) == f for f in VISOR):
            continue
        a, z = t - 0.1, t + 1.6
        if not ok(a, z) or caras_de is None:
            continue
        try:
            caras = caras_de((a + z) / 2)
        except Exception:
            caras = []
        if not caras:
            continue
        x0, y0, x1, y1 = caras[0]
        out.append({'pieza': 'editorial', 'remotion': 'EditorialT6', 'capa': 'delante', 'ini': round(a, 3), 'fin': round(z, 3),
                    'motivo': f'visor sobre la cara: «{" ".join(_limpio(x[2]) for x in todas[i:i + 2])}»',
                    'valores': {'tipo': 'visor', 'caja': [round(x0, 4), round(y0, 4), round(x1, 4), round(y1, 4)]}})
        ultimo = t
    # 2) la barra de búsqueda: «comenta CONTENIDO», «comment "content"»
    for i, (t, p, txt, nb, j) in enumerate(todas):
        if p not in COMENTA or t < dur * 0.4:
            continue
        sig = [x for x in todas[i + 1:i + 5] if x[1] not in DIR.CONECTORAS and x[1] not in ('la', 'palabra', 'the', 'word', 'me', 'aqui', 'abajo', 'below')]
        if not sig or len(sig[0][1]) < 3:
            continue
        palabra = _limpio(sig[0][2]).lower()
        a = t - 0.2
        z = max(sig[0][0] + 2.6, a + 2.6)
        if ok(a, z):
            out.append({'pieza': 'editorial', 'remotion': 'EditorialT6', 'capa': 'delante', 'ajustar': True, 'alto': 0.07, 'ini': round(a, 3),
                        'fin': round(z, 3), 'motivo': f'barra de búsqueda: «{palabra}»', 'valores': {'tipo': 'buscar', 'texto': palabra, 'y': 40.0}})
            break
    # 3) el perfil: la cifra de seguidores que se dice
    for i, (t, p, txt, nb, j) in enumerate(todas):
        valor = _cifra_con_mil(todas, i)
        if valor is None:
            continue
        etiqueta = next((SEGUIDORES[x[1]] for x in todas[i + 1:i + 4] if x[1] in SEGUIDORES), None)
        if not etiqueta or cara_de is None:
            continue
        a, z = t - 0.3, t + 2.8
        if not ok(a, z):
            continue
        img = cara_de(t)
        if not img:
            continue
        out.append({'pieza': 'editorial', 'remotion': 'EditorialT6', 'capa': 'delante', 'ajustar': True, 'alto': 0.1, 'ini': round(a, 3),
                    'fin': round(z, 3), 'motivo': f'perfil: {valor} {etiqueta}',
                    'valores': {'tipo': 'perfil', 'valor': valor, 'etiqueta': etiqueta, 'cara': img.get('cara', ''), 'usuario': str(usuario or '')[:28],
                                'y': 18.0}})
        break
    # 4) la píldora del equipo, bajo el caption («el equipo», «mis clientes»)
    n_eq, ult = 0, -99.0
    for nb, b in enumerate(bl):
        if n_eq >= 2 or b['ini'] - ult < 12.0 or b['ini'] < 1.0:
            continue
        w = next((w for w in b['palabras'] if _p(w['texto']) in EQUIPO), None)
        if w is None:
            continue
        a, z = b['ini'], b['fin'] + 0.3
        if z - a < 1.0 or not ok(a, z, 0.5):
            continue
        out.append({'pieza': 'acomp', 'remotion': 'EditorialT6', 'capa': 'delante', 'ini': round(a, 3), 'fin': round(z, 3),
                    'motivo': f'equipo: «{_limpio(w["texto"])}»', '_bajo': (b['ini'], b['fin']),
                    'valores': {'tipo': 'equipo', 'texto': _limpio(w['texto']).lower(), 'y': 66.0, 'escala': 1.0}})
        n_eq, ult = n_eq + 1, b['ini']
    return out
