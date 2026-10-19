# CineCaptions · By Cinema Productions
# 1_codigo/kit_neon.py — v5.5.13: el Tema 1 NEÓN para CUALQUIER video, con el motor del kit «TEMA 1» del usuario (Remotion: KitNeon.tsx).
"""
Pedido (2026-10-18): «tiene que lograr esto exactamente igual (entregas/3_neon_kinetic_hook.mp4) para que sea reutilizable para cualquier video».
El kit dibuja con su motor (graficos/motor.js, portado tal cual a remotion/src/kitneon/motor.ts); lo que en el kit escribía a mano un editor
(escenas.js: qué bloque, con qué tipografías, tamaños, pegatinas y trazos) aquí lo decide el programa con las palabras de la voz:

    escena_captions(palabras, idioma, fin_video) -> [{'fn': 'hook', 'a': {...}}]       un bloque hook() por frase

Los bloques salen de kinetic_planificador (frases, palabra fuerte, receta neón, qué palabra va en cada hueco y cuándo entra) y se traducen a los
items del kit: versalitas espaciadas ('esp'), serif cursiva ('serif'), palabra enorme con degradado ('big', lima / magenta / blanca con trama),
pegatina inclinada ('stk', roja / lima / magenta / blanca), palabra a mano ('script') y trazos que se dibujan ('circulo', 'lazo', 'subraya').
Tamaños con la regla del ejemplo (medidos con sus fuentes): la palabra grande llena hasta ~900 px (tope 200 px de letra; 250 el gancho, 300 el
cierre), la pegatina ~60 % de ella, serif 80 px, a mano 120 px. Nada por debajo de y = 1560 ni por encima de 220 px (interfaz de Instagram).
"""
from functools import lru_cache
from pathlib import Path

import kinetic_planificador as KP

FUENTES = Path(__file__).resolve().parent.parent / '2_recursos' / 'edicion_pro' / 'kit_neon' / 'fuentes'
ANCHO_UTIL = 900.0                  # px que puede ocupar una línea (el bloque mide 1000 y las letras grandes casi lo llenan)
TOP = 1150                          # arriba del bloque (kit: 1130–1180)
SUELO = 1560                        # nada importante por debajo (interfaz de Instagram)
TECHO = 220

# clip del pack Kinetic (receta) → item del kit
FILL = {'lima': 'acento', 'magenta': 'acento2', 'blanco': 'blanco', 'amarillo': 'acento', 'rojo': 'acento2'}
BG = {'rojo': 'rojo', 'blanco': 'blanco', 'magenta': 'acento2', 'lima': 'acento', 'amarillo': 'acento'}
GIRO_STK = {'rojo': -4, 'blanco': 5, 'acento2': -3, 'acento': -4}
COLOR = {'lima': '#D6FF3B', 'magenta': '#FF2DCB'}


def carpeta_fuentes():
    """Las fuentes del kit: en el .exe van con los recursos (sys._MEIPASS/edicion_pro/kit_neon/fuentes), no junto a este .py (v5.5.14: en el
    programa instalado `FUENTES` no existía → «OSError: cannot open resource» y el Tema 1 salía con los captions viejos de Fusion)."""
    try:
        from sfx_rules import base_recursos
        p = Path(base_recursos()) / 'edicion_pro' / 'kit_neon' / 'fuentes'
        if p.is_dir():
            return p
    except Exception:
        pass
    return FUENTES


@lru_cache(maxsize=8)
def _fuente(nombre):
    from PIL import ImageFont
    return ImageFont.truetype(str(carpeta_fuentes() / nombre), 100)


def ancho(texto, tipo, px):
    """Ancho (px) de `texto` a `px` de letra con la fuente del kit de ese tipo."""
    f = _fuente({'big': 'cond.ttf', 'stk': 'cond.ttf', 'serif': 'serif.ttf', 'script': 'script.ttf'}.get(tipo, 'inter.ttf'))
    t = texto.upper() if tipo in ('big', 'stk', 'esp') else texto
    w = f.getlength(t) * px / 100.0
    return w * 1.42 if tipo == 'esp' else w


def _encaja(texto, tipo, px, maximo=ANCHO_UTIL, minimo=40):
    w = ancho(texto, tipo, px)
    return int(max(minimo, min(px, px * maximo / w if w > 0 else px)))


def _alto(item):
    """Alto aproximado (px) que ocupa un item en la pila (line-height del CSS del kit)."""
    fs = float(item.get('size') or {'esp': 34, 'big': 170, 'serif': 78, 'script': 120, 'stk': 96}[item['k']])
    lh = {'esp': 1.0 * fs + 10, 'big': 0.86 * fs, 'serif': 1.04 * fs, 'script': 0.95 * fs, 'stk': 1.15 * fs}[item['k']]
    return lh + float(item.get('mt') or 0) * fs


def _tiempos(pal, idx):
    return [round(float(pal[i]['t']), 3) for i in idx]


def _cifras(texto):
    """Los números de 2 a 99 dichos con letra, en cifra («tres jóvenes» → «3 jóvenes»); «un/una/uno» no (son artículos)."""
    import edicion_pro_planificador as PL
    out = []
    for p in str(texto).split():
        limpio = p.strip('.,;:!?¡¿"\'')
        v = PL.NUM_PALABRAS.get(PL.plegar(limpio))
        if isinstance(v, int) and 2 <= v <= 99 and PL.plegar(limpio) not in PL._NO_CIFRA:
            p = p.replace(limpio, str(v))
        out.append(p)
    return ' '.join(out)


def bloque_hook(b, pal, primero=False, ultimo=False):
    """Un bloque de kinetic_planificador -> los argumentos de hook() del kit."""
    items, pos = [], {}
    for k, l in enumerate(b['lineas']):
        clave = str(l.get('k') or '')
        texto = str(l.get('texto') or '').strip()
        if not texto:
            continue
        var = clave.split()[-1]
        idx = list(l.get('idx') or [])
        ts = _tiempos(pal, idx) if idx else [round(float(l['t']), 3)]
        texto = _cifras(texto)                                     # (kit: «3 JÓVENES», no «TRES JÓVENES»)
        if l.get('nombre') == 'heroe' and idx and '?' in str(pal[idx[-1]].get('signo') or '') and not texto.endswith('?'):
            texto += '?'                                           # (kit: «XELA?»: la pregunta se queda en la grande)
        if l.get('nombre') == 'heroe':
            tope = 300 if ultimo else 250 if primero else 200
            it = {'k': 'big', 'txt': texto, 't': ts[0], 'size': _encaja(texto, 'big', tope), 'fill': FILL.get(var, 'blanco')}
            pals = texto.split()
            if len(pals) == len(ts) > 1 and '%' not in texto:
                it['t'] = ts                                       # (v5.5.17: «3 JÓVENES»: cada palabra cuando se dice)
            if len(pals) > 1 and pals[0].strip('.,').isdigit():
                it['fills'] = ['acento'] + [it['fill']] * (len(pals) - 1)     # (kit: la cifra en el acento, el resto en su color)
        elif clave.startswith('k tape'):
            bg = BG.get(var, 'rojo')
            heroe = next((x for x in items if x['k'] == 'big'), None)
            px = int((heroe['size'] if heroe else 170) * 0.6)
            it = {'k': 'stk', 'txt': texto, 't': ts[0], 'bg': bg, 'size': _encaja(texto, 'stk', px, 760), 'rot': GIRO_STK.get(bg, -4), 'mt': -0.18}
        elif clave.startswith('k script'):
            it = {'k': 'script', 'txt': texto, 't': ts[0], 'size': _encaja(texto, 'script', 120, 760), 'fill': FILL.get(var, 'acento'), 'rot': -7}
            if items and items[-1]['k'] == 'big':
                it['mt'] = -0.22                                   # (kit: «CONCIERTOS / en vivo» se monta un poco sobre la grande)
        elif clave.startswith('k serif'):
            it = {'k': 'serif', 'txt': texto, 't': ts if len(ts) > 1 else ts[0], 'size': _encaja(texto, 'serif', 80)}
        else:                                                      # k label / k sup: versalitas espaciadas
            it = {'k': 'esp', 'txt': texto, 't': ts[0], 'size': _encaja(texto, 'esp', 34, 940, 22)}
        it['_ts'] = ts
        pos[k] = len(items)
        items.append(it)
    if not items:
        return None
    # el kit nunca apila dos líneas de versalitas ni pone versalitas DEBAJO de la grande (ahí va serif): se juntan / pasan a serif
    visto_big, juntos, nuevo_pos = False, [], {}
    for k_src, it in sorted(((k, items[i]) for k, i in pos.items()), key=lambda x: pos[x[0]]):
        if it['k'] == 'big':
            visto_big = True
        elif it['k'] == 'esp' and visto_big:
            it = dict(it, k='serif', size=_encaja(it['txt'], 'serif', 80))
        prev = juntos[-1] if juntos else None
        if prev is not None and prev['k'] == 'esp' and it['k'] == 'esp' and len((prev['txt'] + ' ' + it['txt']).split()) > 4:
            it = dict(it, k='serif', size=_encaja(it['txt'], 'serif', 80))       # (kit: versalitas de 3–4 palabras como mucho; lo demás, serif)
        if prev is not None and prev['k'] == it['k'] and it['k'] in ('esp', 'serif'):
            prev['txt'] = f"{prev['txt']} {it['txt']}"
            prev['_ts'] = prev['_ts'] + it['_ts']
            prev['size'] = _encaja(prev['txt'], prev['k'], 80 if prev['k'] == 'serif' else 34, 940 if prev['k'] == 'esp' else ANCHO_UTIL, 22 if prev['k'] == 'esp' else 40)
        else:
            juntos.append(dict(it))
        nuevo_pos[k_src] = len(juntos) - 1
    for it in juntos:                                              # serif: un tiempo por palabra (kit); el resto, el de la primera
        ts = it.pop('_ts')
        it['t'] = ts if it['k'] == 'serif' and len(ts) > 1 and len(ts) == len(it['txt'].split()) else ts[0]
    items, pos = juntos, nuevo_pos
    deco = []
    for l in b['lineas']:
        clave = str(l.get('k') or '')
        if not (clave.startswith('k ring') or clave.startswith('k line')):
            continue
        sobre = l.get('sobre', 0)
        refs = [pos[i] for i in (sobre if isinstance(sobre, (list, tuple)) else [sobre]) if i in pos]
        if not refs:
            continue
        var = clave.split()[-1]
        tipo = 'lazo' if 'lazo' in clave else 'subraya' if clave.startswith('k line') else 'circulo'
        d = {'k': tipo, 'i': refs, 't': round(float(l['t']), 3)}
        if var == 'magenta':
            d['color'] = COLOR['magenta']
        deco.append(d)
    alto = sum(_alto(it) for it in items)
    top = max(TECHO, min(TOP, SUELO - alto))
    return {'top': int(top), 'items': items, 'deco': deco, 'tout': round(float(b['t1']), 3)}


def escena_captions(palabras, idioma='es', fin_video=None, mains=None):
    """[{'fn': 'hook', 'a': {...}}] para todo el video (tiempos en s del video)."""
    res = KP.planificar(palabras, idioma=idioma, ancla='bajo', mains=mains, fin_video=fin_video, con_bloques=True)
    bloques, pal = res.get('bloques') or [], res.get('pal') or []
    out = []
    for i, b in enumerate(bloques):
        a = bloque_hook(b, pal, primero=(i == 0), ultimo=(i == len(bloques) - 1))
        if a and str(idioma or 'es')[:2] == 'es' and a['items']:
            # v5.5.17 (kit: «¿Vives o estás / de paso por / XELA?»): la pregunta se abre con «¿» al principio del bloque
            if any(str(it['txt']).rstrip().endswith('?') for it in a['items']) and not any('¿' in str(it['txt']) for it in a['items']):
                it0 = a['items'][0]
                it0['txt'] = '¿' + str(it0['txt']).lstrip()
                if it0['k'] in ('esp', 'serif') and it0.get('size'):
                    it0['size'] = min(int(it0['size']), _encaja(it0['txt'], it0['k'], 34 if it0['k'] == 'esp' else 80, 940 if it0['k'] == 'esp' else ANCHO_UTIL,
                                                              22 if it0['k'] == 'esp' else 40))
        if a:
            t0 = round(float(b['t0']), 3)
            for it in a['items'] + a['deco']:              # v5.5.17: nada del bloque antes de que el bloque entre (t0 va tras la salida del
                tt = it.get('t')                           # anterior; «esto» dicho 0,37 s antes salía ENCIMA de «HACIENDO porque» que aún no se iba)
                if isinstance(tt, list):
                    it['t'] = [max(t0, float(x)) for x in tt]
                elif tt is not None:
                    it['t'] = max(t0, float(tt))
            tout = float(a.get('tout') or 0)
            quedan = []
            for d in a['deco']:                            # v5.5.17: un trazo que empezaba en los últimos 0,15 s se dibujaba con el texto ya
                ref = [a['items'][i] for i in d.get('i') or [] if i < len(a['items'])]   # yéndose: una raya suelta. Entra 0,5 s antes de la salida
                ti = max((min(x['t']) if isinstance(x['t'], list) else float(x['t']) for x in ref), default=t0)
                if d.get('t') is not None and float(d['t']) > tout - 0.5:
                    d['t'] = round(max(tout - 0.5, ti + 0.05), 3)
                if d.get('t') is None or tout - float(d['t']) >= 0.4:
                    quedan.append(d)                       # (sin 0,4 s para dibujarse antes de irse, mejor sin trazo)
            a['deco'] = quedan
            out.append({'fn': 'hook', 'a': a, 't0': t0, 't1': round(float(b['t1']), 3), 'receta': b.get('receta')})
    return out


def bloques_pro(escena, alto=1920.0):
    """Los bloques como edicion_pro._bloques_captions (para la «Píldora» del menú lateral): ini/fin (s), arriba/abajo (fracción del alto), xs y
    palabras [(texto, s)]."""
    out = []
    for e in escena or []:
        a = e.get('a') or {}
        items = a.get('items') or []
        if not items:
            continue
        top = float(a.get('top') or 0)
        pal = []
        for it in items:
            ws = str(it.get('txt') or '').split()
            ts = it.get('t') if isinstance(it.get('t'), list) else [it.get('t')] * len(ws)
            grande = it.get('k') in ('big', 'stk')                    # (v5.5.17: la píldora no repite lo que ya va en grande)
            pal += [(x, float(t if t is not None else e.get('t0', 0)), grande) for x, t in zip(ws, list(ts) + [ts[-1] if ts else None] * len(ws))]
        ult = items[-1]
        ancho_max = max(ancho(str(it.get('txt') or ''), it['k'] if it['k'] in ('big', 'stk', 'serif', 'script') else 'esp',
                              float(it.get('size') or 80)) for it in items) / 1080.0
        out.append({'ini': float(e.get('t0', 0)), 'fin': float(a.get('tout', e.get('t1', 0))), 'arriba': top / alto,
                    'abajo': (top + sum(_alto(it) for it in items)) / alto, 'xs': [max(0.0, 0.5 - ancho_max / 2), 0.5, min(1.0, 0.5 + ancho_max / 2)],
                    'palabras': pal,
                    # v5.5.20 («Captions detrás de ti»): el alto de la línea de ABAJO y si es la palabra GRANDE (la cabeza solo tapa la grande)
                    'linea': max(0.02, _alto(ult) / alto), 'grande_abajo': ult.get('k') in ('big', 'stk'),
                    'ini_clip': max(0.0, float(e.get('t0', 0)) - ANTES_S), 'salida': DESPUES_S})
    return out


ANTES_S = 0.15                      # el clip empieza un poco antes de la primera palabra (la máscara ya está lista)
DESPUES_S = 0.5                     # y acaba cuando ya salió (salida del kit: 0,32 s; los trazos, 0,3 s)


def piezas(escena):
    """Los bloques -> piezas de la Edición PRO: un clip «KitNeon» (Remotion, ProRes 4444 con alfa) por bloque, alternando PRO-SUBS / PRO-SUBS2 (la
    salida de un bloque se monta con la entrada del siguiente, como en el kit). En el clip, el tiempo 0 es `ini` (t0 de la composición)."""
    out = []
    for k, e in enumerate(escena or []):
        a = e.get('a') or {}
        ini = round(max(0.0, float(e.get('t0', 0.0)) - ANTES_S), 3)
        fin = round(min(float(a.get('tout', ini + 1.0)) + DESPUES_S, float(e.get('fin_clip', 1e9))), 3)     # (el del cierre se queda hasta el final)
        if fin - ini < 0.4:
            continue
        texto = ' '.join(str(it.get('txt') or '') for it in a.get('items') or [])
        out.append({'pieza': 'neon', 'remotion': 'KitNeon', 'capa': 'subs' if k % 2 == 0 else 'subs2', 'ini': ini, 'fin': fin,
                    'motivo': f'caption neón «{texto[:40]}»', 'valores': {'escena': [{'fn': e.get('fn', 'hook'), 'a': a}], 't0': ini, 'tema': 'neon'}})
    return out
