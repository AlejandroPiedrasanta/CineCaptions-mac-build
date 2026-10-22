# CineCaptions · By Cinema Productions
# 1_codigo/director_sonido_diseno.py — «AI Sound Director», FASE 3: qué suena y qué se queda en silencio, evento por evento, en los 6 temas.
"""
disenar(analisis, ctx) → {'eventos', 'captions', 'motions', 'viejos', 'resumen'}

Lee lo que GO ya decidió —los cues del tema con sus clips de animación REALES (Kinetic: héroe / anillo / cinta; VIRAL: shatter / select / drag /
negrita; «guion»: la palabra clave con su zoom), las piezas de la PRO con sus tiempos (`edicion_pro_sonido.momentos`, el mismo «cuándo» que usa la
PRO), los eventos visuales de Efectos y los cortes— y la PALETA del proyecto (fase 1).

    captions   CAPTION_SOUND_SCORE 0–1 por caption (papel narrativo, importancia de la frase, tamaño / zoom / clip de la palabra clave, cifra, anillo,
               distancia al último acento). Por debajo del umbral de la paleta: LEAVE_SILENT (la mayoría). El acento de cada tema sale de su carácter:
               golpe diseñado (impacto alto), pop (medio), tic de interfaz (sobrio) o trazo de pluma (editorial); en VIRAL, el de su clip.
    motions    cada movimiento con su importancia (escena entera > tarjeta > icono > tic) y su sitio libre (no pisa un acento de caption).
    encima     un riser en el gancho (una vez), el MOTIVO tonal del video en los datos y en el cierre, whooshes en los cortes que respiran.
    densidad   como mucho 2 + 4·densidad sonidos por ventana de 10 s (se quitan los de menos importancia; golpes y risers mandan).

Cada evento: tipo (golpe, whoosh, giro, riser, trazo, acento, tick, pop), instante, ancla (el fotograma que manda), duración EXACTA de su
animación, pista AI, nivel bajo la voz, parámetros de síntesis (easing, dirección, peso, brillo, semilla), decisión GENERATE y su porqué.
Los sonidos de Simple en cada caption reciben REPLACE / REMOVE con su motivo (los de Efectos y la PRO, en director_sonido.al_colocar / sonidos_pro).

Lo que pide el usuario en la página (fase 6, el 5 % humano) entra aquí:
    controles   {'estilo': auto|limpio|cinematico|energico|minimo, 'intensidad' / 'densidad' / 'voz': auto|poco|medio|mucho} (música y ambiente:
                fase 4). AUTO = lo que decidió la IA. El estilo mueve la paleta; la intensidad, el nivel y el peso (no cambia el carácter del tema);
                la densidad, el umbral y el tope por ventana; la voz, cuánto se apartan los sonidos cuando ella habla.
    ajustes     {clave_de_evento: {'silenciar', 'bloqueado' + 'plan' (el evento ya hecho, no se rehace), 'params' (MENOS / MÁS), 'dur_k', 'semilla'}}
    ronda       sube con «Rediseñar sonido»: otras variaciones de todo lo que no esté bloqueado.
"""
import hashlib

import numpy as np

import director_sonido_eventos as EV

TIPOS = ('golpe', 'whoosh', 'giro', 'riser', 'trazo', 'acento', 'tick', 'pop')
IMPORTANCIA_MOTION = {'escena': 0.7, 'whoosh_grande': 0.65, 'whoosh': 0.5, 'pop': 0.42, 'tick': 0.35, 'golpe': 0.6}
CLAVE_PRO = {'whoosh': 'whoosh', 'pop': 'pop', 'pin': 'pop', 'click': 'tick', 'ui': 'tick', 'corte': 'tick', 'hit': 'golpe', 'tecla': 'tick',
             'cash': 'acento', 'error': None, 'riser': None}          # error: el modo gris ya se ve; un zumbido sobra · riser: lo decide el director
CLIP_VIRAL = {'v shatter': ('golpe', 0.2), 'v drag': ('whoosh', 0.12), 'v select': ('tick', 0.1), 'v negrita': ('pop', 0.05)}
VISUAL_FX = {'corte': ('whoosh', 0.55), 'enfasis': ('whoosh', 0.4), 'broll': ('whoosh', 0.45), 'icono': ('pop', 0.4), 'pegatina': ('pop', 0.4),
             'numero': ('tick', 0.42)}
CHOQUE_S = 0.15                       # un motion menor no suena a menos de esto de un acento de caption
ESTILOS = {'limpio': {'impacto': -0.25, 'densidad': -0.1, 'ui': 0.2, 'reverb': -0.1},
           'cinematico': {'impacto': 0.2, 'reverb': 0.2, 'transitorios': 0.1, 'densidad': -0.05},
           'energico': {'densidad': 0.2, 'transitorios': 0.2, 'motion': 0.2, 'impacto': 0.1},
           'minimo': {'densidad': -0.3, 'impacto': -0.1, 'motion': -0.2}}
DENSIDAD = {'poco': 0.1, 'medio': 0.35, 'mucho': 0.7}
INTENSIDAD = {'poco': (-4.0, 0.8), 'medio': (0.0, 1.0), 'mucho': (3.0, 1.15)}        # (dB para todos, factor de peso del golpe)
VOZ = {'poco': (1.0, 1.0), 'medio': (0.0, 2.0), 'mucho': (-3.0, 5.0)}              # (dB para todos, dB más si cae sobre una palabra)


def _semilla(*partes):
    return int(hashlib.sha1('|'.join(str(p) for p in partes).encode('utf-8')).hexdigest()[:8], 16)


def clave(e):
    """La identidad de un evento entre un diseño y el siguiente (para sus ajustes): origen, caption, tipo e instante (a 0,1 s)."""
    return f"{e.get('origen')}|{e.get('ref')}|{e.get('tipo')}|{round(float(e.get('ancla') or 0.0), 1)}"


def con_controles(analisis, controles):
    """La PALETA con el estilo que pidió el usuario encima (AUTO = la de la IA). No toca el análisis original."""
    c = controles or {}
    estilo = ESTILOS.get(c.get('estilo') or 'auto')
    if not estilo and c.get('densidad') not in DENSIDAD:
        return analisis
    a = dict(analisis)
    v = dict(((analisis.get('paleta') or {}).get('valores') or {}))
    for k, d in (estilo or {}).items():
        v[k] = round(float(np.clip(float(v.get(k, 0.5)) + d, 0, 1)), 3)
    if c.get('densidad') in DENSIDAD:
        v['densidad'] = DENSIDAD[c['densidad']]
    a['paleta'] = dict(analisis.get('paleta') or {}, valores=v)
    return a


def caracter(analisis, controles=None):
    """Cómo suena el ACENTO de caption de ESTE tema (de su identidad, nada fijo por número de tema) y cuánto se permite."""
    analisis = con_controles(analisis, controles)
    c = controles or {}
    r = analisis.get('rasgos') or {}
    v = (analisis.get('paleta') or {}).get('valores') or {}
    impacto, ui = float(v.get('impacto', 0.5)), float(v.get('ui', 0.5))
    if r.get('modo_pro') == 'editorial':
        acento, motivo = 'trazo', 'PRO editorial: cálido y acústico, una pluma en vez de un golpe'
    elif impacto >= 0.6:
        acento, motivo = 'golpe', f'impacto {impacto:.2f}: la palabra grande pega'
    elif r.get('modo_pro') == 'sobria' or (ui >= 0.6 and impacto < 0.45):
        acento, motivo = 'tick', f'sobrio / interfaz (ui {ui:.2f}): un toque nítido, nada de golpes'
    elif impacto >= 0.42:
        acento, motivo = 'pop', f'impacto medio ({impacto:.2f}): la palabra aparece con cuerpo, sin golpe'
    else:
        acento, motivo = 'tick', f'impacto bajo ({impacto:.2f}): solo un toque'
    return {'acento': acento, 'por_que': motivo, 'estilo': r.get('estilo'), 'modo_pro': r.get('modo_pro'),
            'riser': impacto >= 0.45 and r.get('modo_pro') not in ('sobria', 'editorial'),
            'cortes_cada_s': 6.0 if float(v.get('motion', 0.5)) >= 0.45 else 10.0,
            'cortes_whoosh': float(v.get('transitorios', 0.5)) >= 0.6 and r.get('modo_pro') not in ('sobria', 'editorial'),
            'sobrio': r.get('modo_pro') in ('sobria', 'editorial'),
            'densidad': float(v.get('densidad', 0.3)), 'impacto': impacto, 'brillo': float(v.get('brillo', 0.5)), 'reverb': float(v.get('reverb', 0.5)),
            'nivel_extra_db': INTENSIDAD.get(c.get('intensidad'), (0.0, 1.0))[0] + VOZ.get(c.get('voz'), (0.0, 2.0))[0],
            'peso_k': INTENSIDAD.get(c.get('intensidad'), (0.0, 1.0))[1], 'sobre_voz_db': VOZ.get(c.get('voz'), (0.0, 2.0))[1],
            'controles': {k: c.get(k) for k in ('estilo', 'intensidad', 'densidad', 'voz') if c.get(k) not in (None, 'auto')}}


def _momento_caption(c, car, fps):
    """El instante que manda en un caption, su clip y su energía visual: {'t', 'ancla', 'tipo', 'bono', 'texto', 'anillo', 'cinta', 'que'} o None."""
    runs = [r for r in (c.get('runs') or []) if isinstance(r, dict)]
    estilo = car['estilo']
    if estilo in ('kinetic', 'viral') and not any(r.get('k') for r in runs):   # v5.37: los bloques de GO aún sin los clips del tema (Tema 1 neón: los
        linea = next((l for l in (c.get('lines') or []) if isinstance(l, dict) and l.get('role') == 'main'), None)    # captions los arma el kit
        if linea is not None:                                                 # en la PRO): la palabra principal entra con el «pop» del héroe
            t = float(linea.get('start') or c.get('start') or 0.0)
            a = EV.ANIM_KINETIC['pop']
            return {'t': t, 'ancla': t + (0.37 * a['f'] / fps if estilo == 'kinetic' else 0.05), 'tipo': car['acento'] if estilo == 'kinetic' else 'pop',
                    'bono': 0.1, 'size': 0.25, 'texto': str(linea.get('text') or ''), 'que': 'entra la palabra principal', 'anillo': None, 'cinta': None}
    if estilo == 'kinetic':
        con_k = [r for r in runs if r.get('k')]
        heroe = next((r for r in con_k if str(r['k']).startswith('k hero')), None) or max(con_k, key=lambda r: float(r.get('size') or 0), default=None)
        if heroe is None:
            return None
        t = float(heroe.get('t') or c.get('start') or 0.0)
        size = float(heroe.get('size') or 0.2)
        a = EV.ANIM_KINETIC['pop']
        return {'t': t, 'ancla': t + 0.37 * a['f'] / fps, 'tipo': car['acento'], 'bono': float(np.clip((size - 0.2) * 0.8, 0, 0.2)), 'size': size,
                'texto': str(heroe.get('texto') or ''), 'que': f"el héroe entra con «pop» {a['f']} f easeOutBack (×2,6, giro −4°)",
                'anillo': next((r for r in con_k if EV.anim_de_clip(r['k']) == 'trazo'), None),
                'cinta': next((r for r in con_k if EV.anim_de_clip(r['k']) == 'giro'), None)}
    if estilo == 'viral':
        mejor = None
        for r in runs:
            clip = ' '.join(str(r.get('k') or '').split()[:2])
            if clip in CLIP_VIRAL and (mejor is None or CLIP_VIRAL[clip][1] > CLIP_VIRAL[mejor[0]][1]):
                mejor = (clip, r)
        if mejor is None:
            return None                                                   # solo la pila fina: no hay palabra protagonista
        clip, r = mejor
        tipo, bono = CLIP_VIRAL[clip]
        t = float(r.get('t') or c.get('start') or 0.0)
        return {'t': t, 'ancla': t + (0.1 if tipo == 'whoosh' else 0.05), 'tipo': tipo, 'bono': bono, 'size': float(r.get('size') or 0.1),
                'texto': str(r.get('texto') or ''), 'que': f'la palabra clave entra con «{clip[2:]}»', 'anillo': None, 'cinta': None}
    main = next((r for r in runs if r.get('rol') == 'main'), None)
    if main is not None:                                                  # «guion» (Temas 2, 4, 5, 6): la palabra clave con su zoom
        zoom = float(main.get('zoom') or 1.0)
        t = float(main.get('t') or c.get('start') or 0.0)
        return {'t': t, 'ancla': t + 0.05, 'tipo': car['acento'], 'bono': float(np.clip((zoom - 1.0) * 0.5, 0, 0.2)), 'size': zoom,
                'texto': str(main.get('texto') or ''), 'que': f'la palabra clave aparece a ×{zoom:.2f}', 'anillo': None, 'cinta': None}
    lineas = [l for l in (c.get('lines') or []) if isinstance(l, dict) and l.get('role') == 'main']
    if lineas:                                                            # 3 líneas: la principal
        t = float(lineas[0].get('start') or c.get('start') or 0.0)
        return {'t': t, 'ancla': t + 0.04, 'tipo': car['acento'], 'bono': 0.0, 'size': 1.0, 'texto': str(lineas[0].get('text') or ''),
                'que': 'entra la línea principal', 'anillo': None, 'cinta': None}
    return None


def _en_voz(palabras, t):
    return any(float(p.get('start') or 0) <= t <= float(p.get('end') or 0) for p in palabras or [])


def disenar(analisis, ctx, fps=30.0, controles=None, ajustes=None, ronda=0):
    """El diseño de sonido de ESTE video (ver el docstring del módulo). Nunca cambia lo visual: solo lee."""
    car = caracter(analisis, controles)
    analisis = con_controles(analisis, controles)
    narr = analisis.get('narrativa') or {}
    frases = narr.get('frases') or []
    dur = float((analisis.get('voz') or {}).get('duracion') or 0.0) or float((ctx.get('palabras') or [{}])[-1].get('end') or 0.0)
    densidad, impacto, brillo, reverb = car['densidad'], car['impacto'], car['brillo'], car['reverb']
    umbral = 0.55 + 0.3 * (0.4 - densidad)
    palabras = ctx.get('palabras') or []
    eventos, viejos, captions, motions = [], [], [], []
    nota = (523.25 if brillo >= 0.5 else 392.0) * (0.75 if car['modo_pro'] == 'editorial' else 1.0)   # el MOTIVO del video: siempre la misma nota

    def ev(tipo, t, ancla, d, motivo, imp, origen, ref=None, **params):
        params.setdefault('brillo', brillo)
        params['semilla'] = _semilla(tipo, round(ancla, 3), ref, ctx.get('video'), *((ronda,) if ronda else ()))
        if 'peso' in params:
            params['peso'] = round(float(np.clip(params['peso'] * car['peso_k'], 0.2, 1.0)), 3)
        sobre = _en_voz(palabras, ancla)
        rel = EV.NIVEL_REL_VOZ[tipo] + car['nivel_extra_db'] - (car['sobre_voz_db'] if tipo not in ('golpe', 'riser') and sobre else 0.0)
        rel -= max(0.0, car['sobre_voz_db'] - 2.0) * 0.3 if tipo == 'golpe' and sobre else 0.0     # (voz «máxima»: hasta el golpe se aparta un poco)
        eventos.append({'id': f'{tipo}-{len(eventos) + 1:02d}', 'tipo': tipo, 't': round(max(0.0, t), 3), 'ancla': round(ancla, 3), 'dur': round(d, 3),
                        'pista': EV.PISTA[tipo], 'nivel_rel_voz_db': round(rel, 1),
                        'params': params, 'decision': 'GENERATE', 'por_que': motivo, 'importancia': round(float(imp), 2), 'origen': origen, 'ref': ref})
        return eventos[-1]

    # --- intro / outro de Efectos con su sonido propio: se respetan (van pegados a su animación)
    fx_ev = [e for e in ((ctx.get('plan_efectos') or {}).get('eventos') or []) if isinstance(e, dict)]
    intro_sonido = next((e for e in fx_ev if e.get('tipo') == 'sonido' and not e.get('extra') and float(e.get('ini') or 0) < 1.0), None)
    fin_intro = float(intro_sonido.get('pico') or intro_sonido.get('dur') or 0.8) + 0.25 if intro_sonido else 0.0

    # --- captions
    ultimo, n_datos, gancho_usado = -99.0, 0, False
    for i, c in enumerate(ctx.get('bloques') or []):
        if not isinstance(c, dict):
            continue
        viejos_c = [e for e in (c.get('sfx_eventos') or []) if isinstance(e, dict)]
        m = _momento_caption(c, car, fps)
        if m is None:
            for e in viejos_c:
                viejos.append({'cue': i, 'viejo': e.get('sfx_nombre') or e.get('sfx'), 't': e.get('t'), 'decision': 'REMOVE',
                               'por_que': 'el caption no tiene palabra protagonista: el sonido de Simple sobra'})
            continue
        t = m['t']
        rol, imp, _frase = EV._rol_en(frases, t)
        if i == 0:
            rol = 'HOOK'
        cifra = any(ch.isdigit() for ch in m['texto'])
        peso_rol = EV.PESO_ROL.get(rol, 0.0)
        if rol == 'HOOK' and gancho_usado:
            peso_rol = 0.15                                           # el gancho se marca UNA vez; los que siguen, como uno más
        s = 0.15 + peso_rol + 0.25 * float(imp) + m['bono'] + (0.1 if m['anillo'] else 0.0) + (0.15 if cifra else 0.0)
        hueco = t - ultimo
        s -= 0.35 if hueco < 3.0 else (0.15 if hueco < 5.0 else 0.0)
        if hueco < 2.0 and not cifra:
            s = min(s, umbral - 0.01)                                 # dos acentos a menos de 2 s se pisan (salvo una cifra)
        if t < fin_intro:
            s = min(s, umbral - 0.01)                                 # la intro de Efectos ya suena aquí
        s = float(np.clip(s, 0, 1))
        info = {'cue': i, 't': round(t, 3), 'texto': m['texto'], 'rol': rol, 'caption_sound_score': round(s, 2)}
        if s < umbral:
            info['decision'] = 'LEAVE_SILENT'
            info['por_que'] = (f'score {s:.2f} < {umbral:.2f}' + (f' (otro acento hace {hueco:.1f} s)' if hueco < 5 else '') +
                               (' (suena la intro)' if t < fin_intro else '') + f': {rol.lower()}, lo dice la voz y el tema ya lo anima')
            for e in viejos_c:
                viejos.append({'cue': i, 'viejo': e.get('sfx_nombre') or e.get('sfx'), 't': e.get('t'), 'decision': 'REMOVE',
                               'por_que': 'un sonido en casi cada caption cansa y tapa la voz: este caption va en silencio'})
            captions.append(info)
            continue
        tipo = m['tipo']
        info['decision'] = 'REPLACE' if viejos_c else 'GENERATE'
        info['por_que'] = f'score {s:.2f} ≥ {umbral:.2f}: {rol.lower()}' + (' con cifra' if cifra else '') + (' y anillo' if m['anillo'] else '')
        if tipo == 'golpe':
            pre = 0.09
            peso = float(np.clip(0.35 + 1.4 * float(m['size'] if car['estilo'] == 'kinetic' else 0.25) * impacto, 0.3, 1.0))
            ev('golpe', m['ancla'] - pre, m['ancla'], 0.6, f"«{m['texto']}» ({rol.lower()}): {m['que']}; el golpe cae cuando llega a su tamaño, "
               f"con {int(pre * 1000)} ms de aire antes; peso {peso:.2f}", s, 'caption', i, peso=peso, cola=0.35 + 0.3 * reverb, pre=pre,
               brillo=float(np.clip(brillo + (0.25 if car['estilo'] == 'viral' else 0.0), 0, 1)))
        elif tipo == 'whoosh':
            d = 0.3
            ev('whoosh', m['ancla'] - 0.55 * d, m['ancla'], d + 0.12, f"«{m['texto']}» ({rol.lower()}): {m['que']}: aire corto que arrastra la palabra",
               s, 'caption', i, direccion=0.6, easing='easeOutCubic', peso=0.35)
        elif tipo == 'trazo':
            ev('trazo', m['ancla'] - 0.02, m['ancla'], 0.32, f"«{m['texto']}» ({rol.lower()}): {m['que']}: una pluma sobre papel, no un golpe", s,
               'caption', i, potencia=2.0, brillo=min(brillo, 0.45))
        else:
            ev(tipo, m['ancla'], m['ancla'], 0.25 if tipo == 'tick' else 0.3, f"«{m['texto']}» ({rol.lower()}): {m['que']}: {car['por_que']}", s, 'caption', i)
        for e in viejos_c:
            viejos.append({'cue': i, 'viejo': e.get('sfx_nombre') or e.get('sfx'), 't': e.get('t'), 'decision': 'REPLACE',
                           'por_que': f'el sonido genérico se cambia por un {tipo} diseñado para ESTE momento (tiempo, tamaño y paleta)'})
        ultimo = t
        gancho_usado = gancho_usado or rol == 'HOOK'
        if m['anillo'] is not None and rol in ('HOOK', 'DATA', 'REVEAL', 'CTA'):
            ta = float(m['anillo'].get('t') or t)
            ev('trazo', ta, ta, EV.ANIM_KINETIC['trazo']['s'] + 0.05, 'el anillo se dibuja en 0,45 s frenando (1 − (1 − p)^2,4): rotulador con esa energía',
               s * 0.8, 'caption', i, potencia=2.4)
        if m['cinta'] is not None and rol in ('HOOK', 'REVEAL', 'CTA'):
            tc = float(m['cinta'].get('t') or t)
            f = EV.ANIM_KINETIC['giro']['f']
            ev('giro', tc, tc + 0.6 * f / fps, f / fps + 0.05, f'la cinta entra girada −9° en {f} f: whoosh que da la vuelta y el slap al pegarse',
               s * 0.7, 'caption', i)
        if rol == 'DATA' and n_datos < 3:
            ev('acento', m['ancla'] + 0.02, m['ancla'], 1.1, 'motivo de los datos: la misma nota en cada cifra (identidad del video)', s * 0.7, 'dato', i, nota=nota)
            n_datos += 1
        captions.append(info)
    acentos = [e for e in eventos if e['origen'] == 'caption' and e['tipo'] in ('golpe', 'pop', 'tick', 'trazo', 'whoosh')]

    # --- el gancho: un riser corto que acaba en el primer acento fuerte (si llega pronto y el tema lo pide)
    golpes = [e for e in acentos if e['tipo'] == 'golpe']
    if car['riser'] and not intro_sonido and golpes and 0.9 < golpes[0]['ancla'] <= 4.0:
        g = golpes[0]
        d = min(1.6, g['ancla'] - 0.05)
        ev('riser', g['ancla'] - d, g['ancla'], d, f'gancho: sube {d:.1f} s y se corta 30 ms antes del primer golpe (payoff)', 0.9, 'gancho')
    # --- el cierre: el motivo, más largo, en la última llamada a la acción con sonido
    cta = [c for c in captions if c['rol'] == 'CTA' and c.get('decision') != 'LEAVE_SILENT']
    if cta:
        tf = cta[-1]['t'] + 0.15
        ev('acento', tf, tf, 1.6, 'cierre (CTA): el motivo del video, más largo — firma sonora del final', 0.8, 'cierre', cta[-1]['cue'], nota=nota * 0.75)

    # --- motions de la PRO (el mismo «cuándo» que usa la PRO) y de Efectos
    pro = ctx.get('plan_pro') or {}
    candidatos = []                                                       # (tipo, t_ancla, dur, importancia, motivo, params)
    transiciones = []
    if pro.get('piezas'):
        try:
            import edicion_pro_sonido as PS
            momentos, transiciones = PS.momentos({'piezas': pro['piezas'], 'tema5': pro.get('tema5')}, ())
        except Exception:
            momentos = []
        for k_pro, t, nivel, largo, _ancla, que in momentos:
            tipo = CLAVE_PRO.get(k_pro, 'tick')
            if tipo is None:
                motions.append({'t': round(float(t), 3), 'que': que, 'decision': 'LEAVE_SILENT', 'por_que': 'se ve solo; un sonido aquí sobra'})
                continue
            if car['sobrio'] and tipo == 'whoosh' and str(que).startswith('sale'):
                motions.append({'t': round(float(t), 3), 'que': que, 'decision': 'LEAVE_SILENT', 'por_que': 'tema sobrio: solo suena lo que entra'})
                continue
            grande = k_pro == 'whoosh' and nivel >= -10.5
            imp = IMPORTANCIA_MOTION['whoosh_grande' if grande else tipo]
            if tipo == 'whoosh' and str(que).startswith('entra'):
                imp += 0.1                                            # lo que ENTRA manda (la escena que llega se oye; la que se va, menos)
            elif tipo == 'whoosh' and str(que).startswith('sale'):
                imp -= 0.1
            d = float(largo or 0.5) if tipo == 'whoosh' else 0.3
            candidatos.append((tipo, float(t), d, imp, f'PRO: {que}', {'peso': 0.55 if grande else 0.35, 'direccion': 0.0}))
    for e in fx_ev:
        tp = e.get('tipo')
        if tp not in VISUAL_FX:
            continue
        tipo, imp = VISUAL_FX[tp]
        a, d = float(e.get('ini') or 0.0), float(e.get('dur') or 0.5)
        ancla = a + (min(d, 0.6) / 2 if tp == 'corte' else 0.1)
        claro = str(e.get('asset') or '') in ('destello', 'glitch')
        candidatos.append((tipo, ancla, min(0.6, max(0.25, d)) if tipo == 'whoosh' else 0.25, imp, f"Efectos: {tp} «{e.get('asset') or ''}»",
                           {'peso': 0.4, 'brillo': float(np.clip(brillo + (0.2 if claro else 0.0), 0, 1)), 'direccion': 0.0}))
    lado = 1.0
    for tipo, t, d, imp, motivo, params in sorted(candidatos, key=lambda x: x[1]):
        cerca = [e for e in eventos if abs(e['ancla'] - t) < CHOQUE_S]
        if cerca:
            motions.append({'t': round(t, 3), 'que': motivo, 'decision': 'LEAVE_SILENT', 'por_que': f"pisaría «{cerca[0]['id']}» (a menos de {CHOQUE_S:.2f} s)"})
            continue
        if tipo == 'whoosh':
            params['direccion'] = lado * 0.7
            lado = -lado
            ev('whoosh', t - 0.55 * d, t, d + 0.12, f'{motivo}: aire con el pico en el movimiento ({d:.2f} s)', imp, 'motion', None, easing='easeInOutCubic', **params)
        elif tipo == 'golpe':
            ev('golpe', t - 0.05, t, 0.5, f'{motivo}: un golpe suave', imp, 'motion', None, pre=0.05, cola=0.25, **{k: v for k, v in params.items() if k != 'direccion'})
        else:
            ev(tipo, t, t, 0.25, f'{motivo}: toque de interfaz a la medida', imp, 'motion', None, **{k: v for k, v in params.items() if k not in ('peso', 'direccion')})
        motions.append({'t': round(t, 3), 'que': motivo, 'decision': 'GENERATE', 'id': eventos[-1]['id']})
    # risers antes de las escenas grandes de la PRO: como mucho uno cada 20 s, nunca encima de un golpe de caption (no en temas sobrios)
    if car['riser']:
        ultimo_r = -99.0
        for t, que in sorted(transiciones):
            t = float(t)
            if (t < 2.0 or t - ultimo_r < 20.0 or any(e['tipo'] == 'riser' and abs(e['ancla'] - t) < 8.0 for e in eventos)
                    or any(e['tipo'] == 'golpe' and e['origen'] == 'caption' and abs(e['ancla'] - t) < 2.5 for e in eventos)):
                continue
            ev('riser', t - 1.2, t, 1.2, f'transición grande de la PRO ({que}): la tensión sube y se corta justo al entrar', 0.55, 'motion')
            ultimo_r = t
    # --- cortes de escena que respiran (sin otra transición): aire, de lado alterno — solo en temas enérgicos (en uno sobrio, un corte seco no
    #     tiene movimiento que suene: sería un sonido sin causa)
    ultimo_w = -99.0
    for tc in sorted(float(x) for x in (ctx.get('cortes') or []) if car['cortes_whoosh']):
        if (tc - ultimo_w < car['cortes_cada_s'] or tc < 1.0 or any(abs(tc - e['ancla']) < 0.6 for e in eventos)
                or any(e['origen'] == 'motion' and e['tipo'] in ('whoosh', 'riser', 'golpe') and abs(tc - e['ancla']) < 1.5 for e in eventos)):
            continue
        d = 0.42
        ev('whoosh', tc - d * 0.55, tc, d + 0.12, f'corte de escena a {tc:.2f} s: aire que pasa con easeInOutCubic (pico en el corte), de lado alterno', 0.5,
           'corte', None, direccion=lado * 0.8, easing='easeInOutCubic', peso=0.4)
        lado, ultimo_w = -lado, tc

    # --- lo que el usuario pidió para cada evento (página AI Sound Director): silenciar, bloquear, MENOS / MÁS, regenerar
    for e in eventos:
        aj = (ajustes or {}).get(clave(e)) or {}
        if not aj:
            continue
        e['clave'] = clave(e)
        if aj.get('silenciar'):
            e['decision'] = 'LEAVE_SILENT'
            e['por_que'] += ' — SILENCIADO por ti'
            e['ajustado'] = True
            continue
        if aj.get('params'):
            e['params'].update(aj['params'])
            e['ajustado'] = True
        if aj.get('dur_k'):
            e['dur'] = round(max(0.08, e['dur'] * float(aj['dur_k'])), 3)
        if aj.get('semilla') is not None:
            e['params']['semilla'] = int(aj['semilla'])
        if aj.get('bloqueado'):
            e['bloqueado'] = True
            if isinstance(aj.get('plan'), dict):
                e['plan_fijo'] = dict(aj['plan'])
    # --- densidad: como mucho 2 + 4·densidad sonidos por ventana de 10 s; compiten por importancia (solo el gancho, el cierre y lo bloqueado van fijos)
    tope = int(round(2 + 4 * densidad))
    eventos.sort(key=lambda e: e['t'])
    fijos = {e['id'] for e in eventos if e['origen'] in ('gancho', 'cierre') or e.get('bloqueado') or e.get('ajustado')}   # (lo retocado por el usuario se queda)
    if golpes and any(e['origen'] == 'gancho' for e in eventos):
        fijos.add(golpes[0]['id'])                                    # el golpe que remata el riser del gancho
    for k0 in np.arange(0, max(dur, 1.0), 10.0):
        dentro = [e for e in eventos if k0 <= e['ancla'] < k0 + 10 and e['decision'] == 'GENERATE']
        sobran = max(0, len(dentro) - tope)
        for e in sorted((e for e in dentro if e['id'] not in fijos), key=lambda e: (e['importancia'], -e['t']))[:sobran]:
            e['decision'] = 'REMOVE'
            e['por_que'] += f' — QUITADO: más de {tope} sonidos en {int(k0)}–{int(k0) + 10} s (pesa menos que los que quedan)'
    for info in captions:                                             # sin su acento, el caption entero va en silencio (anillo, cinta y nota también)
        if info.get('decision') == 'LEAVE_SILENT':
            continue
        suyos = [e for e in eventos if e.get('ref') == info['cue'] and e['origen'] in ('caption', 'dato')]
        if suyos and suyos[0]['decision'] == 'REMOVE':
            for e in suyos:
                if e['decision'] == 'GENERATE':
                    e['decision'] = 'REMOVE'
                    e['por_que'] += ' — QUITADO: su caption se quedó sin acento'
            info['decision'] = 'LEAVE_SILENT'
            info['por_que'] += ' → LEAVE_SILENT: no cupo en su ventana de 10 s'
            for v in viejos:
                if v['cue'] == info['cue'] and v['decision'] == 'REPLACE':
                    v['decision'] = 'REMOVE'
    activos = [e for e in eventos if e['decision'] == 'GENERATE']
    resumen = {'captions': len(captions), 'con_sonido': sum(1 for c in captions if c['decision'] != 'LEAVE_SILENT'),
               'en_silencio': sum(1 for c in captions if c['decision'] == 'LEAVE_SILENT'), 'eventos': len(activos),
               'motions': len(motions), 'motions_con_sonido': sum(1 for m in motions if m['decision'] == 'GENERATE' and
                                                                   any(e['id'] == m.get('id') and e['decision'] == 'GENERATE' for e in eventos)),
               'por_tipo': {t: sum(1 for e in activos if e['tipo'] == t) for t in sorted({e['tipo'] for e in activos})},
               'por_origen': {o: sum(1 for e in activos if e['origen'] == o) for o in sorted({e['origen'] for e in activos})},
               'viejos': {d: sum(1 for x in viejos if x['decision'] == d) for d in ('REPLACE', 'REMOVE', 'KEEP')}, 'umbral': round(umbral, 2),
               'acento': car['acento'], 'por_que_acento': car['por_que'], 'intro_de_efectos': bool(intro_sonido), 'controles': car['controles'],
               'ronda': int(ronda or 0), 'ajustados': sum(1 for e in eventos if e.get('ajustado') or e.get('bloqueado'))}
    for e in eventos:
        e.setdefault('clave', clave(e))
    return {'eventos': eventos, 'captions': captions, 'motions': motions, 'viejos': viejos, 'caracter': car, 'resumen': resumen}
